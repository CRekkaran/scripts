#!/usr/bin/env python

'''Read a line formated like a spearmint results.dat line,
construct the corresponding model, run the model with cross validation,
and print the results; dies with error if parameters are invalid'''

import sys
sys.path.append('..') #train
import re,argparse, tempfile, os,glob
import makemodel
import socket
import train
import numpy as np
import sklearn.metrics
import scipy.stats
import calctop

class Bunch(object):
  def __init__(self, adict):
    self.__dict__.update(adict)


parser = argparse.ArgumentParser(description='Run single model line and report results.')
parser.add_argument('--line',type=str,help='Complete line',required=True)
parser.add_argument('--seed',type=int,help='Random seed',default=0)
parser.add_argument('--split',type=int,help='Which predefined split to use',default=0)
parser.add_argument('--data_root',type=str,help='Location of gninatypes directory',default='')

args = parser.parse_args()

linevals = args.line.split()[2:]

opts = makemodel.getoptions()

if len(linevals) != len(opts):
    print "Wrong number of options in line (%d) compared to options (%d)" %(len(linevals),len(opts))

params = dict()
for (i,(name,vals)) in enumerate(sorted(opts.items())):
    v = linevals[i]
    if type(vals) == tuple:
        if type(vals[0]) == int:
            v = int(v)
        elif type(vals[0]) == float:
            v = float(v)
    elif isinstance(vals, makemodel.Range):
        v = float(v)
    params[name] = v


params = Bunch(params)

model = makemodel.create_model(params)

host = socket.gethostname() 
d = tempfile.mkdtemp(prefix=host+'-',dir='.')

os.chdir(d)
mfile = open('model.model','w')
mfile.write(model)
mfile.close()

#get hyperparamters
base_lr = 10**params.base_lr_exp
momentum=params.momentum
weight_decay = 10**params.weight_decay_exp
solver = params.solver

#setup training
prefix = '../data/all_0.5_%d_'%args.split
trainargs = train.parse_args(['--seed',str(args.seed),'--prefix',prefix,'--data_root',
    args.data_root,'-t','1000','-i','100000','-m','model.model',
    '--reduced','-o',d,'--momentum',str(momentum),'--weight_decay',str(weight_decay),
    '--base_lr',str(base_lr),'--solver',solver])

train_test_files = train.get_train_test_files(prefix=prefix, foldnums=None, allfolds=False, reduced=True, prefix2=None)
if len(train_test_files) == 0:
    print "error: missing train/test files",prefix
    sys.exit(1)


outprefix = d

test_aucs, train_aucs = [], []
test_rmsds, train_rmsds = [], []
test_y_true, train_y_true = [], []
test_y_score, train_y_score = [], []
test_y_aff, train_y_aff = [], []
test_y_predaff, train_y_predaff = [], []
topresults = []

#train each pair
numfolds = 0
for i in train_test_files:

    outname = '%s.%s' % (outprefix, i)
    results = train.train_and_test_model(trainargs, train_test_files[i], outname)
    test, trainres = results

    if not np.isfinite(np.sum(trainres.y_score)):
        print "Non-finite trainres score"
        sys.exit(-1)
    if not np.isfinite(np.sum(test.y_score)):
        print "Non-finite test score"
        sys.exit(-1)
    if not np.isfinite(np.sum(trainres.y_predaff)):
        print "Non-finite trainres aff"
        sys.exit(-1)
    if not np.isfinite(np.sum(test.y_predaff)):
        print "Non-finite test aff"
        sys.exit(-1)                        

    #aggregate results from different crossval folds
    if test.aucs:
        test_aucs.append(test.aucs)
        train_aucs.append(trainres.aucs)
        test_y_true.extend(test.y_true)
        test_y_score.extend(test.y_score)
        train_y_true.extend(trainres.y_true)
        train_y_score.extend(trainres.y_score)

    if test.rmsds:
        test_rmsds.append(test.rmsds)
        train_rmsds.append(trainres.rmsds)
        test_y_aff.extend(test.y_aff)
        test_y_predaff.extend(test.y_predaff)
        train_y_aff.extend(trainres.y_aff)
        train_y_predaff.extend(trainres.y_predaff)
        
    #run model to get calctop
    #first fine last model
    lastiter = 0
    cmodel = None
    for fname in glob.glob('*.%d_iter_*.caffemodel'%i):
        nums=(re.findall('\d+', fname ))
        new_iter=int(nums[-1])
        if new_iter>lastiter:
            lastiter=new_iter
            cmodel = fname
    topresults += calctop.evaluate_fold(train_test_files[i]['test'], cmodel, 'model.model',args.data_root)
    

R = scipy.stats.pearsonr(test_y_aff, test_y_predaff)[0]
rmse = np.sqrt(sklearn.metrics.mean_squared_error(test_y_aff, test_y_predaff))
auc = sklearn.metrics.roc_auc_score(test_y_true, test_y_score)
top = calctop.find_top_ligand(topresults,1)/100.0

print d, R, rmse, auc, top

