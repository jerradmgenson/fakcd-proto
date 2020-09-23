"""
Perform preprocessing activities that occur after feature selection.
Ergo, this script is designed to be run after (and informed by) the
Feature Selection notebook. The input of this script is the output
of preprocess_stage1.py. The output of this script is the input of
gen_model.py.

Preprocessing steps performed by this script include:
- Discard all columns except those in SUBSET_COLUMNS.
- Discard all rows containing NAs.
- Discard all rows where trestbps is equal to 0.
- Convert cp to a binary class.
- Convert restecg to a binary class.
- Optionally convert target to a binary or ternary class.
- Rescale binary and ternary classes to range from -1 to 1.
- Randomize the row order.
- Split data into testing, training, and validation sets.

Copyright 2020 Jerrad M. Genson

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""

import enum
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

# Path to the output validation dataset.
VALIDATION_DATASET_PATH = GIT_ROOT / Path('build/validation_data.csv')

# Columns to subset from the original input dataset.
SUBSET_COLUMNS = ['age', 'sex', 'cp', 'thalrest', 'trestbps', 'restecg', 'fbs',
                  'thalach', 'exang', 'oldpeak', 'target']

# Fraction of data to use for testing (as a real number between 0 and 1).
TESTING_FRACTION = 0.2

# Fraction of data to use for validation (as a real number between 0 and 1).
VALIDATION_FRACTION = 0.2

# Integer to use for seeding the random number generator.
RANDOM_SEED = 667252912

# Enumerates possible values for 'CLASSIFICATION_TYPE'.
class ClassificationType(enum.Enum):
    # Classification using 2 target classes.
    BINARY = enum.auto()

    # CLassification using 3 target classes.
    TERNARY = enum.auto()

    # Classification using all possible target classes.
    MULTICLASS = enum.auto()

# Set what type of classification target to generate.
# Possible values are the members of ClassificationType.
CLASSIFICATION_TYPE = ClassificationType.BINARY


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
    data_subset.loc[data_subset['fbs'] == 0, 'fbs'] = -1

    if CLASSIFICATION_TYPE == ClassificationType.BINARY:
        # Convert target (heart disease class) to a binary class.
        data_subset.loc[data_subset['target'] != 0, 'target'] = 1
        data_subset.loc[data_subset['target'] == 0, 'target'] = -1

    elif CLASSIFICATION_TYPE == ClassificationType.TERNARY:
        # Convert target to a ternary class.
        data_subset.loc[data_subset['target'] == 0, 'target'] = -1
        data_subset.loc[data_subset['target'] == 1, 'target'] = 0
        data_subset.loc[data_subset['target'] > 1, 'target'] = 1

    elif CLASSIFICATION_TYPE != ClassificationType.MULTICLASS:
        # Invalid classification type.
        raise ValueError(f'Unknown classification type `{CLASSIFICATION_TYPE}`.')

    # Shuffle order of rows in dataset.
    data_subset = data_subset.sample(frac=1)

    # Split dataset into testing, training, and validation sets.
    testing_rows = ceil(len(data_subset) * TESTING_FRACTION)
    validation_rows = ceil(len(data_subset) * VALIDATION_FRACTION) + testing_rows
    testing_data = data_subset[:testing_rows]
    validation_data = data_subset[testing_rows:validation_rows]
    training_data = data_subset[validation_rows:]

    # Save testing/training/validation datasets to CSV files.
    testing_data.to_csv(TESTING_DATASET_PATH, index=False)
    validation_data.to_csv(VALIDATION_DATASET_PATH, index=False)
    training_data.to_csv(TRAINING_DATASET_PATH, index=False)


if __name__ == '__main__':  # pragma: no cover
    main()
