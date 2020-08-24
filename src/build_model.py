import random
import argparse
import logging
import pickle
import time
import subprocess
import multiprocessing
import os
from pathlib import Path
from collections import namedtuple

import numpy as np
import pandas as pd
from sklearn import svm
from sklearn.model_selection import GridSearchCV
from sklearn.neighbors import KNeighborsClassifier
from sklearn.linear_model import SGDClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler


DATASET_COLUMNS = ['age', 'sex', 'cp', 'trestbps', 'chol', 'fbs', 'restecg', 'thalach', 'exang', 'oldpeak', 'slope', 'ca', 'thal', 'target']
DEFAULT_COLUMNS = ['age', 'sex', 'cp', 'trestbps', 'chol', 'fbs', 'restecg', 'thalach', 'exang', 'oldpeak', 'slope']
GITHUB_URL = 'https://github.com/jerradmgenson/cardiac'
MODEL_BASE_NAME = 'heart_disease_model'
SVC_PARAMETER_GRID = [
    {'C': [0.001, 0.1, 0.5, 1, 2, 10, 100, 1000], 'kernel': ['linear'], 'cache_size': [500]},
    {'C': [0.001, 0.1, 0.5, 1, 2, 10, 100, 1000], 'kernel': ['rbf', 'sigmoid'], 'gamma': [0.001, 0.0001], 'cache_size': [500]},
    {'C': [0.001, 0.1, 0.5, 1, 2, 10, 100, 1000], 'kernel': ['poly'], 'gamma': [0.001, 0.0001], 'degree': [2, 3, 4], 'cache_size': [500]},
]

KNC_PARAMETER_GRID = [
    {'n_neighbors': [3, 5, 10, 15], 'weights': ['uniform', 'distance'],  'algorithm': ['ball_tree', 'kd_tree', 'brute'], 'p': [1, 2, 3]}
]

SGD_PARAMETER_GRID = [
    {'loss': ['hinge', 'log', 'modified_huber', 'squared_hinge', 'perceptron'], 'penalty': ['l1', 'l2', 'elasticnet'], 'alpha': 10.0**-np.arange(1,7), 'max_iter': [1500, 2000]},
]

RFC_PARAMETER_GRID = [
    {'n_estimators': [50, 100, 200], 'max_features': [None, 'sqrt'], 'max_samples': [0.1, 0.4, 0.8, 1], 'criterion': ['gini', 'entropy'], 'min_samples_split': [2, 4, 8]},
]

Model = namedtuple('Model', 'class_ name abbreviation parameter_grid')

MODELS = (Model(svm.SVC, 'support vector machine', 'svc', SVC_PARAMETER_GRID),
          Model(KNeighborsClassifier, 'k-nearest neighbors', 'knc', KNC_PARAMETER_GRID),
          Model(RandomForestClassifier, 'random forest', 'rfc', RFC_PARAMETER_GRID),
          Model(SGDClassifier, 'stochastic gradient descent', 'sgc', SGD_PARAMETER_GRID))


def main():
    start_time = time.time()
    command_line_arguments = parse_command_line()
    configure_logging(command_line_arguments.log_level)
    print('Loading cardiac dataset from {}'.format(command_line_arguments.input_path))
    cardiac_dataset = pd.read_csv(str(command_line_arguments.input_path))
    print('Done loading cardiac dataset.')
    if command_line_arguments.columns:
        reduced_dataset = cardiac_dataset[command_line_arguments.columns + ['target']]

    else:
        reduced_dataset = cardiac_dataset[DEFAULT_COLUMNS + ['target']]

    random.seed(command_line_arguments.random_seed)
    np.random.seed(command_line_arguments.random_seed)
    shuffled_dataset = reduced_dataset.sample(frac=1)
    input_data = shuffled_dataset.values[:, 0:-1]
    target_data = shuffled_dataset.values[:, -1]
    scaler = StandardScaler().fit(input_data)
    scaled_inputs = scaler.transform(input_data)
    training_rows = int(len(scaled_inputs) * (1 - command_line_arguments.validation_fraction))
    training_inputs = scaled_inputs[:training_rows]
    training_targets = target_data[:training_rows]
    validation_inputs = scaled_inputs[training_rows:]
    validation_targets = target_data[training_rows:]
    commit_hash = get_commit_hash()
    print('Training dataset row count: {}'.format(len(training_inputs)))
    print('Validation dataset row count: {}'.format(len(validation_inputs)))
    print('Random number generator seed: {}'.format(command_line_arguments.random_seed))
    print('Training iterations: {}'.format(command_line_arguments.training_iterations))
    print('Commit hash: {}'.format(commit_hash))
    jobs = []
    for model_args in MODELS:
        if model_args.name == 'stochastic gradient descent':
            model_args.parameter_grid[0]['max_iter'] = [np.ceil(10**6 / len(training_inputs))]

        jobs.extend([(model_args, training_inputs, training_targets)] * command_line_arguments.training_iterations)

    with multiprocessing.Pool(command_line_arguments.cpu) as pool:
        models = pool.map(train_model, jobs)

    best_model = None
    for count, model in enumerate(models):
        if best_model is None or model.best_score > best_model.best_score:
            best_model = model

        if (count + 1) % command_line_arguments.training_iterations == 0:
            best_model.scaler = scaler
            best_model.random_seed = command_line_arguments.random_seed
            best_model.training_iterations = command_line_arguments.training_iterations
            best_model.commit_hash = commit_hash
            best_model.validation = 'UNVALIDATED'
            best_model.url = GITHUB_URL
            best_model.training_inputs = training_inputs
            best_model.training_targets = training_targets
            validate_model(best_model, validation_inputs, validation_targets)
            print_model_results(best_model, best_model.name)
            final_output_path = (command_line_arguments.output_path
                                 / (MODEL_BASE_NAME + '_{}.dat'.format(best_model.abbreviation)))

            save_model(best_model, final_output_path)
            print('Saved {} model to {}'.format(best_model.name, final_output_path))
            best_model = None

    print('Runtime: {} seconds'.format(time.time() - start_time))


def get_commit_hash():
    try:
        if subprocess.check_output(['git', 'diff']).strip():
            return ''

        return subprocess.check_output(['git', 'rev-parse', '--verify', 'HEAD']).decode('utf-8').strip()

    except FileNotFoundError:
        return ''


def print_model_results(model, name):
    print('\nResults for {} model:'.format(name))
    print('Accuracy:    {}'.format(model.accuracy))
    print('Precision:   {}'.format(model.precision))
    print('Sensitivity: {}'.format(model.sensitivity))
    print('Specificity: {}'.format(model.specificity))


def parse_command_line():
    parser = argparse.ArgumentParser(description='Build a machine learning model to predict heart disease.')
    parser.add_argument('input_path', type=Path, help='Path to the input cardiac dataset.')
    parser.add_argument('output_path', type=Path, help='Path to output the heart disease model to.')
    parser.add_argument('--validation_fraction',
                        type=validation_fraction,
                        default=0.2,
                        help='The fraction of the dataset to use for validation as a decimal between 0 and 1.')

    parser.add_argument('--columns',
                        type=dataset_column,
                        nargs='+',
                        help='Columns in the heart disease dataset to use as inputs to the model.')

    parser.add_argument('--random_seed',
                        type=int,
                        default=random.randint(1, 10000000),
                        help='Initial integer to seed the random number generator with.')

    parser.add_argument('--training_iterations',
                        type=int,
                        default=1,
                        help='Number of iterations to use when training the model.')

    parser.add_argument('--cpu',
                        type=int,
                        default=os.cpu_count(),
                        help='Number of processes to use for training models.')

    parser.add_argument('--log_level',
                        choices=('critical', 'error', 'warning', 'info', 'debug'),
                        default='info',
                        help='Log level to configure logging with.')

    return parser.parse_args()


def validation_fraction(n):
    x = float(n)
    if x < 0 or x > 1:
        raise ValueError('validation_fraction must not be less than 0 or greater than 1.')

    return x


def dataset_column(n):
    if n not in DATASET_COLUMNS:
        raise ValueError('column must be one of {}'.format(DATASET_COLUMNS))

    return n


def configure_logging(log_level):
    log_level_number = getattr(logging, log_level.upper())
    logger = logging.getLogger(__name__)
    logger.setLevel(log_level_number)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level_number)
    formatter = logging.Formatter('%(levelname)s: %(message)s')
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger


def train_model(job):
    model_args = job[0]
    training_inputs = job[1]
    training_targets = job[2]
    base_model = model_args.class_()
    grid_estimator = GridSearchCV(base_model, model_args.parameter_grid)
    grid_estimator.fit(training_inputs, training_targets)
    model = grid_estimator.best_estimator_
    model.best_score = grid_estimator.best_score_
    model.name = model_args.name
    model.abbreviation = model_args.abbreviation

    return model


def validate_model(model, input_data, target_data):
    predictions = model.predict(input_data)
    true_positives = 0.0
    true_negatives = 0.0
    false_positives = 0.0
    false_negatives = 0.0
    for prediction, target in zip(predictions, target_data):
        if prediction == 1 and target == 1:
            true_positives += 1.0

        elif prediction == 1 and target == 0:
            false_positives += 1.0

        elif prediction == 0 and target == 1:
            false_negatives += 1.0

        else:
            true_negatives += 1.0

    model.accuracy = (true_positives + true_negatives) / len(input_data)
    model.precision = true_positives / (true_positives + false_positives)
    model.sensitivity = true_positives / (true_positives + false_negatives)
    model.specificity = true_negatives / (true_negatives + false_positives)
    model.validation_inputs = input_data
    model.validation_targets = target_data


def save_model(model, output_path):
    with output_path.open('wb') as output_file:
        pickle.dump(model, output_file)


if __name__ == '__main__':
    main()
