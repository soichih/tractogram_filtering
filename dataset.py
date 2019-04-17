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


#def load_h5_item(h5_filename, idx):
   # f = h5py.File(h5_filename)
   # data = f['data'][idx]
   # label = f['label'][idx]
   # return data, label


# Read numpy array data and label from h5_filename
def load_h5(h5_filename):
    f = h5py.File(h5_filename)
    data = f['data'][:]
    label = f['label'][:]
    return (data, label)



def gen_modelnet_id(root):
    classes = []
    with open(os.path.join(root, 'train_files.txt'), 'r') as f:
        for line in f:
            classes.append(line.strip().split('/')[0])
    classes = np.unique(classes)
    with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), 'modelnet_id.txt'), 'w') as f:
        for i in range(len(classes)):
            f.write('{}\t{}\n'.format(classes[i], i))


class ModelNetDataset(data.Dataset):
    def __init__(self,
                 root,
                 npoints=2500,
                 split='train_files',
                 data_augmentation=True):
        self.npoints = npoints
        self.root = root
        self.split = split
        self.data_augmentation = data_augmentation
        self.fns = []
        #print(self.root)
        with open(os.path.join(root, '{}.txt'.format(self.split)), 'r') as f:
            for line in f:
                self.fns.append(line.strip())
        #print(self.fns)


        self.lengths = []
        for fn in self.fns:
            #print(fn)
            nome_file = os.path.join(root,fn)
            #print(nome_file)
            f = h5py.File(nome_file)
            #self.lengths += len(f['label'][:])
            self.lengths.append(len(f['label'][:]))
        self.lengths = np.array(self.lengths)
        #print(self.lengths[:1].sum())



        
        self.cat = {}
        with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), 'modelnet_id.txt'), 'r') as f:
            for line in f:
                ls = line.strip().split()
                self.cat[ls[0]] = int(ls[1])



        self.classes = list(self.cat.keys())
        print(self.classes)


    
    
        

        self.final_data = np.ndarray([])
        self.final_label = np.ndarray([])
        
        for fn in self.fns:
            nome_file = os.path.join(root,fn)
            [data, label] = load_h5(nome_file)
            if not self.final_data.shape:
                self.final_data = data
                self.final_label = label
            else:
                self.final_data = np.concatenate((self.final_data,data))
                self.final_label = np.concatenate((self.final_label,label))

        

    
    def __getitem__(self, idx):
        
         

        '''
        for i, fn in enumerate(self.fns):
            #print(i)
            #print(fn)
            #print(idx)
            #print(self.lengths[:i+1].sum())
            if idx < self.lengths[:i+1].sum(): #if i=0 self.lengths[:i+1].sum() =    :i+1 = items from the beginning through stop-1
                print(self.lengths[:i+1].sum())
                #print('test')
                pts, cls = load_h5_item(fn, 
                                    idx - self.lengths[:i].sum())
                                    #self.lengths[:i].sum() - idx)
                                    #idx)
        '''
        pts = self.final_data[idx]
        cls = self.final_label[idx]    

        pts = torch.from_numpy(pts.astype(np.float32))
        cls = torch.from_numpy(np.array([cls]).astype(np.int64))

        #sample = {}
        #sample['points'] = pts
        #sample['class'] = cls

        return pts,cls


    def __len__(self):
        return self.lengths.sum()

if __name__ == '__main__':
    dataset = sys.argv[1]
    datapath = sys.argv[2]

    '''
    if dataset == 'shapenet':
        d = ShapeNetDataset(root = datapath, class_choice = ['Chair'])
        print(len(d))
        ps, seg = d[0]
        print(ps.size(), ps.type(), seg.size(),seg.type())

        d = ShapeNetDataset(root = datapath, classification = True)
        print(len(d))
        ps, cls = d[0]
        print(ps.size(), ps.type(), cls.size(),cls.type())
        # get_segmentation_classes(datapath)
    '''

    if dataset == 'modelnet':
        #print('test')
        #gen_modelnet_id(datapath)
        #print(datapath)

        d = ModelNetDataset(root=datapath)
        #print('test')
        print(len(d))
        print(d[0])

