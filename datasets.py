from __future__ import print_function
import torch.utils.data as data
import os
import os.path
import torch
import numpy as np
import sys
from tqdm import tqdm 
import json
from plyfile import PlyData, PlyElement
import h5py

from torch.utils.data import Dataset
import csv
import pickle
import nibabel as nib
import glob
import time

from torch_geometric.data import Data as gData, Batch as gBatch
from torch_geometric.data import Dataset as gDataset
from torch_geometric.nn import knn_graph

from selective_loader import load_selected_streamlines,load_selected_streamlines_uniform_size

class HCP20Dataset(gDataset):
    def __init__(self,
                 sub_file,
                 root_dir,
                 act=True,
                 fold_size=None,
                 transform=None):
        """
        Args:
            root_dir (string): root directory of the dataset.
            transform (callable, optional): Optional transform to be applied
                on a sample.
        """
        self.root_dir = root_dir
        with open(sub_file) as f:
            subjects = f.readlines()
        self.subjects = [s.strip() for s in subjects]
        self.transform = transform
        self.fold_size = fold_size
        self.act = act
        self.fold = []
        self.n_fold = 0
        if fold_size is not None:
            self.load_fold()

    def __len__(self):
        return len(self.subjects)

    def __getitem__(self, idx):
        fs = self.fold_size
        if fs is None:
            return self.getitem(idx)

        fs_0 = (self.n_fold * fs)
        idx = fs_0 + (idx % fs)

        return self.data_fold[idx]

    def load_fold(self):
        fs = self.fold_size
        fs_0 = self.n_fold * fs
        t0 = time.time()
        print('Loading fold')
        self.data_fold = [self.getitem(i) for i in range(fs_0, fs_0 + fs)]
        print('time needed: %f' % (time.time()-t0))

    def getitem(self, idx):
        sub = self.subjects[idx]
        sub_dir = os.path.join(self.root_dir, 'sub-%s' % sub)
        T_file = os.path.join(sub_dir, 'sub-%s_var-HCP_full_tract.trk' % (sub))
        label_file = os.path.join(sub_dir, 'sub-%s_var-HCP_labels.pkl' % (sub))
        #T_file = os.path.join(sub_dir, 'All_%s.trk' % (tract_type))
        #label_file = os.path.join(sub_dir, 'All_%s_gt.pkl' % (tract_type))
        T = nib.streamlines.load(T_file, lazy_load=True)
        with open(label_file, 'rb') as f:
            gt = pickle.load(f)

        sample = {'points': np.arange(T.header['nb_streamlines']), 'gt': gt}

        #t0 = time.time()
        if self.transform:
            sample = self.transform(sample)
        #print('time sampling %f' % (time.time()-t0))

        #t0 = time.time()
        streams, slices = load_selected_streamlines(T_file,
                                                    sample['points'].tolist())
        #print('time loading selected streamlines %f' % (time.time()-t0))
        #t0 = time.time()
        sample['points'] = np.split(streams, slices[:-1], axis=0)
        #print('time numpy split %f' % (time.time()-t0))
        ### create graph structure
        # n = len(sample['points'])
        #sample_flat = torch.from_numpy(np.concatenate(sample['points']))
        #l = sample_flat.shape[0]
        #edges = torch.empty((2, 2*l - 2*n), dtype=torch.long)
        #start = 0
        #i0 = 0
        #for sl in sample['points']:
        #    l_sl = len(sl)
        #    end = start + 2*l_sl - 2
        #    edges[:, start:end] = torch.tensor(
        #                        [range(i0, i0+l_sl-1) + range(i0+1,i0+l_sl),
        #                        range(i0+1,i0+l_sl) + range(i0, i0+l_sl-1)])
        #    start = end
        #    i0 += l_sl
        #t0 = time.time()
        data = []
        for i, sl in enumerate(sample['points']):
            l_sl = len(sl)
            sl = torch.from_numpy(sl)
            edges = torch.tensor([list(range(0, l_sl-1)) + list(range(1,l_sl)),
                                list(range(1,l_sl)) + list(range(0, l_sl-1))],
                                dtype=torch.long)
            data.append(gData(x=sl, edge_index=edges, y=sample['gt'][i]))
        #gt = torch.from_numpy(sample['gt'])
        #graph_sample = gData(x=sample_flat, edge_index=edges, y=gt)
        sample['points'] = gBatch().from_data_list(data)
        #sample['points'] = data
        sample['name'] = 'sub-%s_var-HCP_full_tract' %(sub)
        #print('time building graph %f' % (time.time()-t0))
        return sample
    
    class RndSampling(object):
    """Random sampling from input object to return a fixed size input object
    Args:
        output_size (int): Desired output size.
        maintain_prop (bool): Default True. Indicates if the random sampling
            must be proportional to the number of examples of each class
    """

    def __init__(self, output_size, maintain_prop=True, prop_vector=[]):
        assert isinstance(output_size, (int))
        assert isinstance(maintain_prop, (bool))
        self.output_size = output_size
        self.maintain_prop = maintain_prop
        self.prop_vector = prop_vector

    def __call__(self, sample):
        pts, gt = sample['points'], sample['gt']

        n = pts.shape[0]
        if self.maintain_prop:
            n_classes = gt.max() + 1
            remaining = self.output_size
            chosen_idx = []
            for cl in reversed(range(n_classes)):
                if (gt == cl).sum() == 0:
                    continue
                if cl == gt.min():
                    chosen_idx += np.random.choice(
                        np.argwhere(gt == cl).reshape(-1),
                        int(remaining)).reshape(-1).tolist()
                    break
                prop = float(np.sum(gt == cl)) / n
                k = np.round(self.output_size * prop)
                remaining -= k
                chosen_idx += np.random.choice(
                    np.argwhere(gt == cl).reshape(-1),
                    int(k)).reshape(-1).tolist()

            assert (self.output_size == len(chosen_idx))
            chosen_idx = np.array(chosen_idx)
        elif len(self.prop_vector) != 0:
            n_classes = gt.max() + 1
            while len(self.prop_vector) < n_classes:
                self.prop_vector.append(1)
            remaining = self.output_size
            out_size = self.output_size
            chosen_idx = []
            excluded = 0
            for cl in range(n_classes):
                if (gt == cl).sum() == 0:
                    continue
                if cl == gt.max():
                    chosen_idx += np.random.choice(
                        np.argwhere(gt == cl).reshape(-1),
                        int(remaining)).reshape(-1).tolist()
                    break
                if self.prop_vector[cl] != 1:
                    prop = self.prop_vector[cl]
                    excluded += np.sum(gt == cl)
                    #excluded -= (n-excluded)*prop
                    k = np.round(self.output_size * prop)
                    out_size = remaining - k
                else:
                    prop = float(np.sum(gt == cl)) / (n - excluded)
                    k = np.round(out_size * prop)

                remaining -= k
                chosen_idx += np.random.choice(
                    np.argwhere(gt == cl).reshape(-1),
                    int(k)).reshape(-1).tolist()

            assert (self.output_size == len(chosen_idx))
            chosen_idx = np.array(chosen_idx)
        else:
            chosen_idx = np.random.choice(range(n), self.output_size)

        out_gt = gt[chosen_idx] if type(gt) == int else gt
        return {'points': pts[chosen_idx], 'gt': out_gt}


class TestSampling(object):
    """Random sampling from input object until the object is all sampled
    Args:
        output_size (int): Desired output size.
    """

    def __init__(self, output_size):
        assert isinstance(output_size, (int))
        self.output_size = output_size

    def __call__(self, sample):
        sl = sample['points']

        n = sl.shape[0]
        if self.output_size > len(range(n)):
            chosen_idx = range(n)
        else:
            chosen_idx = np.random.choice(range(n), self.output_size).tolist()
        out_sample = {'points': sl[chosen_idx]}

        if 'gt' in sample.keys():
            out_sample['gt'] = sample['gt'][chosen_idx]
        return out_sample

