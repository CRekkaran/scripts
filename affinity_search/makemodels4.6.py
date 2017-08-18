#!/usr/bin/env python

'''Generate models for affinity predictions'''

# [SGD|Adam] * [regular|rankloss|ranklosswneg] [xaviar|radial] [0.01|0.001]

modelstart = '''layer {
  name: "data"
  type: "MolGridData"
  top: "data"
  top: "label"
  top: "affinity"
  include {
    phase: TEST
  }
  molgrid_data_param {
    source: "TESTFILE"
    batch_size: 10
    dimension: 23.5
    resolution: 0.5
    shuffle: false
    balanced: false
    has_affinity: true
    root_folder: "../../"
  }
}
layer {
  name: "data"
  type: "MolGridData"
  top: "data"
  top: "label"
  top: "affinity"
  include {
    phase: TRAIN
  }
  molgrid_data_param {
    source: "TRAINFILE"
    batch_size:  50
    dimension: 23.5
    resolution: 0.5
    shuffle: true
    balanced: true
    stratify_receptor: true
    stratify_affinity_min: 0
    stratify_affinity_max: 0
    stratify_affinity_step: 0
    has_affinity: true
    random_rotation: true
    random_translate: 2
    root_folder: "../../"
  }
}
'''

endmodel = '''layer {
    name: "split"
    type: "Split"
    bottom: "LASTCONV"
    top: "split"
}

layer {
  name: "output_fc"
  type: "InnerProduct"
  bottom: "split"
  top: "output_fc"
  inner_product_param {
    num_output: 2
    weight_filler {
      type: "xavier"
    }
  }
}
layer {
  name: "loss"
  type: "SoftmaxWithLoss"
  bottom: "output_fc"
  bottom: "label"
  top: "loss"
}

layer {
  name: "output"
  type: "Softmax"
  bottom: "output_fc"
  top: "output"
}
layer {
  name: "labelout"
  type: "Split"
  bottom: "label"
  top: "labelout"
  include {
    phase: TEST
  }
}

layer {
  name: "output_fc_aff"
  type: "InnerProduct"
  bottom: "split"
  top: "output_fc_aff"
  inner_product_param {
    num_output: 1
    weight_filler {
      type: "xavier"
    }
  }
}

layer {
  name: "rmsd"
  type: "AffinityLoss"
  bottom: "output_fc_aff"
  bottom: "affinity"
  top: "rmsd"
  affinity_loss_param {
    scale: 0.1
    gap: 1
    penalty: 0
    pseudohuber: false
    delta: 0
    ranklossmult: RANKLOSS
    ranklossneg: RANKNEG
  }
}

layer {
  name: "predaff"
  type: "Flatten"
  bottom: "output_fc_aff"
  top: "predaff"
}

layer {
  name: "affout"
  type: "Split"
  bottom: "affinity"
  top: "affout"
  include {
    phase: TEST
  }
}

'''

convunit = '''
layer {
  name: "unitNUMBER_pool"
  type: "Pooling"
  bottom: "INLAYER"
  top: "unitNUMBER_pool"
  pooling_param {
    pool: MAX
    kernel_size: 2
    stride: 2
  }
}
layer {
  name: "unitNUMBER_conv1"
  type: "Convolution"
  bottom: "unitNUMBER_pool"
  top: "unitNUMBER_conv1"
  convolution_param {
    num_output: OUTPUT
    pad: 1
    kernel_size: 3
    stride: 1
    weight_filler {
      type: "FILLER"
      symmetric_fraction: FRACTION      
    }
  }
}'''



finishunit = '''
layer {
  name: "unitNUMBER_norm"
  type: "LRN"
  bottom: "unitNUMBER_conv1"
  top: "unitNUMBER_conv1"
}

layer {
 name: "unitNUMBER_scale"
 type: "Scale"
 bottom: "unitNUMBER_conv1"
 top: "unitNUMBER_conv1"
 scale_param {
  bias_term: true
 }
}
layer {
  name: "unitNUMBER_func"
  type: "ELU"
  bottom: "unitNUMBER_conv1"
  top: "unitNUMBER_conv1"
}
''';

# normalization: none, LRN (across and within), Batch
# learning rat
# depth 3, width 32 (doubled)
def create_unit(num, filler, fraction):
    width = 32
    double = True
    ret = convunit.replace('NUMBER', str(num))
    if num == 1:
        ret = ret.replace('INLAYER','data')
    else:
        ret = ret.replace('INLAYER', 'unit%d_conv1'%(num-1))            

    outsize = width
    if double:
        outsize *= 2**(num-1)
    ret = ret.replace('OUTPUT', str(outsize)) 
    ret = ret.replace('FILLER', filler)
    ret = ret.replace('FRACTION', str(fraction))
        
    ret += finishunit.replace('NUMBER', str(num))
    return ret


def makemodel(filler, fraction, ranklossm, rankneg):
    m = modelstart
    depth = 3
    for i in xrange(1,depth+1):
        m += create_unit(i, filler, fraction)
    m += endmodel.replace('LASTCONV','unit%d_conv1'%depth).replace('RANKLOSS',str(ranklossm)).replace('RANKNEG',str(rankneg))
    
    return m
    

models = []
           
# [SGD|Adam] * [regular|rankloss|ranklosswneg] [xaviar|radial|radial.5] [0.01|0.001][

for ranklossm in [0, 0.01,0.1,1]:
    for rankneg in [0,1]:
        if ranklossm == 0 and rankneg == 1:
            continue
        for filler in ['xavier']:
            fraction = 1.0
            if filler == 'radial.5':
                filler = 'radial'
                fraction = 0.5
            model = makemodel(filler, fraction,ranklossm, rankneg)
            m = 'affinity_%.3f_%d.model'%(ranklossm,rankneg)
            models.append(m)
            out = open(m,'w')
            out.write(model)
        
            
for m in models:
    for baselr in [0.01, 0.001]:
        for solver in ['SGD','Adam']:
            print "train.py -m %s -p ../types/all_0.5_0_  --keep_best -t 1000 -i 100000 --solver %s --base_lr %f --reduced -o all_%s_%s_%.3f"%(m,solver, baselr, m.replace('.model',''),solver,baselr)
