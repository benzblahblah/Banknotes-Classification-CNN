import time

import numpy as np

from sklearn.utils import shuffle
from sklearn.metrics import confusion_matrix, classification_report

from matplotlib import pyplot as plt
import itertools

import keras
from keras.models import Sequential
from keras.layers import Input, Dense, Dropout, Flatten, Conv2D, MaxPooling2D
from keras import backend as K

import tensorflow as tf
from tensorflow.python.tools import freeze_graph
from tensorflow.python.platform import gfile

import Dataset


def build_model(img_size, num_channels, num_classes, learning_rate):
    model = Sequential()

    model.add(Conv2D(filters=32, kernel_size=(5, 5), padding='same', activation='relu',
                     input_shape=[img_size, img_size, num_channels]))

    model.add(MaxPooling2D(pool_size=(2, 2), strides=(2, 2), padding='same'))

    model.add(Conv2D(filters=32, kernel_size=(5, 5), padding='same', activation='relu'))

    model.add(MaxPooling2D(pool_size=(2, 2), strides=(2, 2), padding='same'))

    model.add(Conv2D(filters=64, kernel_size=(5, 5), padding='same', activation='relu'))

    model.add(MaxPooling2D(pool_size=(2, 2), strides=(2, 2), padding='same'))

    model.add(Flatten())

    model.add(Dense(1024, activation='relu'))

    model.add(Dropout(0.4))

    model.add(Dense(num_classes, activation='softmax'))

    # Optimizer
    opt = keras.optimizers.Adadelta(lr=learning_rate)

    model.compile(loss=keras.losses.categorical_crossentropy, optimizer=opt,
                  metrics=['accuracy'])

    return model


def train(model, x_train, y_train, x_valid, y_valid, batch_size, epochs, log_dir):
    # Use tensorboard
    # cli => tensorboard --logdir path_to_dir
    tensorboard = keras.callbacks.TensorBoard(log_dir=log_dir, histogram_freq=0, write_graph=True, write_images=True)

    # Train
    # NOTE* - The validation set is checked during training to monitor progress,
    # and possibly for early stopping, but is never used for gradient descent.
    # REF -> https://github.com/keras-team/keras/issues/1753
    model.fit(x_train, y_train, batch_size=batch_size, epochs=epochs, verbose=1,
              validation_data=(x_valid, y_valid), callbacks=[tensorboard])

    return model


def evaluate(model, classes, x_test, y_test):
    print('_________________________________________________________________')
    # Evaluate with testing data
    evaluation = model.evaluate(x_test, y_test)

    print('Summary: Loss over the testing dataset: %.2f, Accuracy: %.2f' % (evaluation[0], evaluation[1]))

    # Get prediction from given x_test
    y_pred = model.predict_classes(x_test)

    # Get report
    print(classification_report(np.argmax(y_test, axis=1), y_pred, target_names=classes))

    # Get confusion matrix
    cm = confusion_matrix(np.argmax(y_test, axis=1), y_pred)
    plot_confusion_matrix(cm, classes)
    print('=================================================================')


def plot_confusion_matrix(cm, classes, normalize=False, title='Confusion matrix', cmap=plt.cm.Blues):
    plt.imshow(cm, interpolation='nearest', cmap=cmap)
    plt.title(title)
    plt.colorbar()
    tick_marks = np.arange(len(classes))
    plt.xticks(tick_marks, classes, rotation=45)
    plt.yticks(tick_marks, classes)

    if normalize:
        cm = cm.astype('float') / cm.sum(axis=1)[:, np.newaxis]
        print('Normalized confusion matrix')
    else:
        print('Confusion matrix, without normalization')

    print(cm)

    thresh = cm.max() / 2.
    for i, j in itertools.product(range(cm.shape[0]), range(cm.shape[1])):
        plt.text(j, i, cm[i, j],
                 horizontalalignment='center',
                 color='white' if cm[i, j] > thresh else 'black')

    plt.tight_layout()
    plt.ylabel('True label')
    plt.xlabel('Predicted label')


def save_model(model, classes, model_name, input_node_names, output_node_name, output_dir):
    prepare_dir(output_dir)

    # Save model config
    model_json = model.to_json()
    with open(output_dir + 'model_config.json', 'w') as f:
        f.write(model_json)

    # Save model summary
    with open(output_dir + 'model_summary.txt', 'w') as f:
        model.summary(print_fn=lambda x: f.write(x + '\n'))

    # Save labels
    with open(output_dir + 'trained_labels.txt', 'w') as f:
        f.write('\n'.join(classes) + '\n')

    # Save trained model with the weights stored as constants
    tf.train.write_graph(K.get_session().graph_def, output_dir, model_name + '_graph.pbtxt')
    tf.train.Saver().save(K.get_session(), output_dir + model_name + '.chkp')

    freeze_graph.freeze_graph(output_dir + model_name + '_graph.pbtxt', None, False,
                              output_dir + model_name + '.chkp', output_node_name, 'save/restore_all', 'save/Const:0',
                              output_dir + 'frozen_' + model_name + '.pb', True, '')


def prepare_dir(path):
    if not gfile.Exists(path):
        gfile.MakeDirs(path)
        print('Created directory ' + path)


def get_model_memory_usage(batch_size, model):
    shapes_mem_count = 0
    for l in model.layers:
        single_layer_mem = 1
        for s in l.output_shape:
            if s is None:
                continue
            single_layer_mem *= s
        shapes_mem_count += single_layer_mem

    trainable_count = np.sum([K.count_params(p) for p in set(model.trainable_weights)])
    non_trainable_count = np.sum([K.count_params(p) for p in set(model.non_trainable_weights)])

    total_memory = 4.0 * batch_size * (shapes_mem_count + trainable_count + non_trainable_count)
    gbytes = np.round(total_memory / (1024.0 ** 3), 3)
    return gbytes


def make_hparam_string(learning_rate, batch_size, epochs):
    # Get current current time
    t = time.strftime('%Y-%m-%d_%H-%M-%S')

    return '%s,lr=%s,b=%d,e=%d/' % (t, learning_rate, batch_size, epochs)


def main():
    print('--start--')

    # Config
    model_name = 'banknotes_convnet'

    img_dir = '../files/thaibaht_photos/'
    output_dir = '../files/models/'
    log_dir = '../files/training_logs/'

    img_size = 128
    num_channels = 3

    batch_size = 32
    epochs = 30  # 30

    learning_rate = 1.0

    validation_percentage = 0.1
    testing_percentage = 0.3

    datasets = Dataset.read_datasets(img_dir, img_size, validation_percentage, testing_percentage)

    classes = datasets.classes
    num_classes = len(classes)

    model = build_model(img_size, num_channels, num_classes, learning_rate)

    # View model
    model.summary()

    # Check memory needed
    print('Approximately memory usage : {} gb'.format(get_model_memory_usage(batch_size, model)))

    # Get data and shuffle
    x_train = datasets.training_data.images_data
    y_train = datasets.training_data.labels_onehot

    x_train, y_train = shuffle(x_train, y_train, random_state=1)

    x_valid = datasets.validation_data.images_data
    y_valid = datasets.validation_data.labels_onehot

    x_valid, y_valid = shuffle(x_valid, y_valid, random_state=2)

    x_test = datasets.testing_data.images_data
    y_test = datasets.testing_data.labels_onehot

    x_test, y_test = shuffle(x_test, y_test, random_state=3)

    # Get folder name
    hparam_str = make_hparam_string(learning_rate, batch_size, epochs)
    log_dir += hparam_str
    output_dir += hparam_str

    model = train(model=model,
                  x_train=x_train, y_train=y_train,
                  x_valid=x_valid, y_valid=y_valid,
                  batch_size=batch_size, epochs=epochs, log_dir=log_dir)

    evaluate(model=model, classes=classes, x_test=x_test, y_test=y_test)

    # Save model as file
    save_model(model, classes, model_name, ['conv2d_1_input'], 'dense_2/Softmax', output_dir)

    plt.show()
    print('--end--')


if __name__ == '__main__':
    main()
