---
license: mit
---

# EMNIST ByClass Dataset

## Authors
- **Gregory Cohen**
- **Saeed Afshar**
- **Jonathan Tapson**
- **Andre van Schaik**

The MARCS Institute for Brain, Behaviour and Development  
Western Sydney University  
Penrith, Australia 2751

Email: g.cohen@westernsydney.edu.au

## What is it?
The EMNIST dataset is a set of handwritten character digits derived from the NIST Special Database 19 ([NIST Special Database 19](https://www.nist.gov/srd/nist-special-database-19)) and converted to a 28x28 pixel image format and dataset structure that directly matches the MNIST dataset ([MNIST](http://yann.lecun.com/exdb/mnist/)). Further information on the dataset contents and conversion process can be found in the paper available at [arXiv:1702.05373v1](https://arxiv.org/abs/1702.05373v1).

## Formats
The version of the dataset is provided in the binary format as the original MNIST dataset as outlined in [MNIST dataset format](http://yann.lecun.com/exdb/mnist/).

## Dataset Summary

- **EMNIST ByClass**: 814,255 characters. 62 unbalanced classes.

Please refer to the EMNIST paper (available at [arXiv:1702.05373v1](https://arxiv.org/abs/1702.05373v1)) for further details of the dataset structure.

## How to cite
Please cite the following paper when using or referencing the dataset:

Cohen, G., Afshar, S., Tapson, J., & van Schaik, A. (2017). EMNIST: an extension of MNIST to handwritten letters. Retrieved from [arXiv:1702.05373](http://arxiv.org/abs/1702.05373)

## Files
The dataset consists of the following files:
- emnist-byclass-mapping.txt
- emnist-byclass-test-images-idx3-ubyte.gz
- emnist-byclass-test-labels-idx1-ubyte.gz
- emnist-byclass-train-images-idx3-ubyte.gz
- emnist-byclass-train-labels-idx1-ubyte.gz


## License and Usage
This copy of dataset is co-located on Hugging Face for non-profitable usage. If there are any conflicts of copyright, please contact me to delete it.