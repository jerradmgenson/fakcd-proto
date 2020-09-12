"""
Perform preprocessing activities that occur after feature selection.
Ergo, this script is designed to be run after (and informed by) the
Feature Selection notebook.

"""

import subprocess
from pathlib import Path
from math import ceil

import numpy as np
import pandas as pd

# Path to the root of the git repository.
GIT_ROOT = subprocess.check_output(['git', 'rev-parse', '--show-toplevel'])
GIT_ROOT = Path(GIT_ROOT.decode('utf-8').strip())

# Path to the input dataset.
INPUT_DATASET_PATH = GIT_ROOT / Path('build/combined_data.csv')

# Path to the output testing dataset.
TESTING_DATASET_PATH = GIT_ROOT / Path('build/testing_data.csv')

# Path to the output training dataset.
TRAINING_DATASET_PATH = GIT_ROOT / Path('build/training_data.csv')

# Columns to subset from the original input dataset.
SUBSET_COLUMNS = ['age', 'sex', 'cp', 'thalrest', 'trestbps', 'restecg', 'fbs',
                  'thalach', 'exang', 'oldpeak', 'num']

# Fraction of data to use for testing (as a real number between 0 and 1).
TESTING_FRACTION = 0.2

# Integer to use for seeding the random number generator.
RANDOM_SEED = 251473927


def main():
    # Seed the random number generator.
    np.random.seed(RANDOM_SEED)

    # Read input data from CSV file.
    dataset = pd.read_csv(INPUT_DATASET_PATH)

    # Discard all columns except those in SUBSET_COLUMNS.
    data_subset = dataset[SUBSET_COLUMNS]

    # Discard all rows that contain NAs.
    data_subset = data_subset.dropna()

    # Discard all rows where resting blood pressue is 0.
    data_subset = data_subset[data_subset.trestbps != 0]

    # Convert chest pain to a binary class.
    data_subset.loc[data_subset['cp'] != 4, 'cp'] = 1
    data_subset.loc[data_subset['cp'] == 4, 'cp'] = -1

    # Convert resting ECG to a binary class.
    data_subset.loc[data_subset['restecg'] != 1, 'restecg'] = -1

    # Rescale binary/ternary classes to range from -1 to 1.
    data_subset.loc[data_subset['sex'] == 0, 'sex'] = -1
    data_subset.loc[data_subset['exang'] == 0, 'exang'] = -1

    # Shuffle order of rows in dataset.
    data_subset = data_subset.sample(frac=1)

    # Split dataset into testing and training sets.
    testing_rows = ceil(len(data_subset) * TESTING_FRACTION)
    testing_data = data_subset[:testing_rows]
    training_data = data_subset[testing_rows:]

    # Save testing/training datasets to CSV files.
    testing_data.to_csv(TESTING_DATASET_PATH, index=None)
    training_data.to_csv(TRAINING_DATASET_PATH, index=None)


if __name__ == '__main__':
    main()