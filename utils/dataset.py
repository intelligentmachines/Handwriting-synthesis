import torch
import numpy as np
from collections import Counter
from torch.utils.data import DataLoader, Dataset
from utils.data_utils import train_offset_normalization, valid_offset_normalization
from utils.constants import Global


class HandwritingDataset(Dataset):
    """Handwriting dataset."""

    def __init__(self, data_path, split='train', text_req=False):
        """
        Args:
            data_path (string): Path to the data folder.
            split (string): train or valid
        """
        self.text_req = text_req

        strokes = np.load(data_path + 'strokes.npy', allow_pickle=True, encoding='bytes')
        with open(data_path + 'sentences.txt') as file:
            texts = file.read().splitlines()

        # list of length of each stroke in strokes
        lengths = [len(stroke) for stroke in strokes]
        max_len = np.max(lengths)
        n_total = len(strokes)

        # Mask
        mask_shape = (n_total, max_len)
        mask = np.zeros(mask_shape, dtype=np.float32)

        # Convert list of str into array of list of chars
        char_seqs = [list(char_seq) for char_seq in texts]
        char_seqs = np.asarray(char_seqs)

        char_lens = [len(char_seq) for char_seq in char_seqs]
        max_char_len = np.max(char_lens)

        # char Mask
        mask_shape = (n_total, max_char_len)  # (6000,64)
        char_mask = np.zeros(mask_shape, dtype=np.float32)

        # Input text array
        inp_text = np.ndarray((n_total, max_char_len), dtype='<U1')
        inp_text[:, :] = ' '

        # Convert list of stroke(array) into ndarray of size(n_total, max_len, 3)
        data_shape = (n_total, max_len, 3)
        data = np.zeros(data_shape, dtype=np.float32)

        for i, (seq_len, text_len) in enumerate(zip(lengths, char_lens)):
            mask[i, :seq_len] = 1.
            data[i, :seq_len] = strokes[i]
            char_mask[i, :text_len] = 1.
            inp_text[i, :text_len] = char_seqs[i]

        # create vocab
        self.id_to_char, self.char_to_id = self.build_vocab(inp_text)

        idx_permute = np.random.permutation(n_total)

        n_train = int(0.9 * data.shape[0])

        if split == 'train':
            self.dataset = data[idx_permute[:n_train]]
            self.mask = mask[idx_permute[:n_train]]
            self.texts = inp_text[idx_permute[:n_train]]
            self.char_mask = char_mask[idx_permute[:n_train]]
            Global.train_mean, Global.train_std, self.dataset = train_offset_normalization(self.dataset)

        elif split == 'valid':
            self.dataset = data[idx_permute[n_train:]]
            self.mask = mask[idx_permute[n_train:]]
            self.texts = inp_text[idx_permute[n_train:]]
            self.char_mask = char_mask[idx_permute[n_train:]]
            self.dataset = valid_offset_normalization(Global.train_mean, Global.train_std, data)

        # divide data into inputs and target seqs
        self.input_data = np.zeros(self.dataset.shape, dtype=np.float32)
        self.input_data[:, 1:, :] = self.dataset[:, :-1, :]
        self.target_data = self.dataset

    def __len__(self):
        return self.input_data.shape[0]

    def idx_to_char(self, id_seq):
        return np.array([self.id_to_char[id] for id in id_seq])

    def char_to_idx(self, char_seq):
        return np.array([self.char_to_id[char] for char in char_seq])

    def build_vocab(self, texts):
        counter = Counter()
        for text in texts:
            counter.update(text)
        unique_char = sorted(counter)
        vocab_size = len(unique_char)

        id_to_char = dict(zip(np.arange(vocab_size), unique_char))
        char_to_id = dict([(v, k) for (k, v) in id_to_char.items()])
        return id_to_char, char_to_id

    def __getitem__(self, idx):
        input_seq = torch.from_numpy(self.input_data[idx])
        target = torch.from_numpy(self.target_data[idx])
        mask = torch.from_numpy(self.mask[idx])

        if self.text_req:
            text = torch.from_numpy(self.char_to_idx(self.texts[idx]))
            char_mask = torch.from_numpy(self.char_mask[idx])
            return (input_seq, target, mask, text, char_mask)
        else:
            return (input_seq, target, mask)
