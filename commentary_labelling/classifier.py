import pickle

import numpy as np
import pandas as pd
from keras.models import load_model
from keras.preprocessing.text import text_to_word_sequence
from commentary_labelling.Logger import Logger

import nltk

# logger = Logger.getInstance()


def load_pkl(filename):
    with open(f"{filename}.pkl", "rb") as f:
        d = pickle.load(f)
    # logger.log(f"Loaded {filename}!")
    return d


class Classifier:
    loaded = False

    _line_ngrams = None
    _length_ngrams = None
    _vocab = None
    _line_model = None
    _length_model = None
    _lemmatizer = None

    def __init__(self):
        pass

    @staticmethod
    def load():
        if not Classifier.loaded:
            Classifier._line_ngrams = load_pkl("../models/line_ngrams")
            Classifier._length_ngrams = load_pkl("../models/length_ngrams")
            Classifier._vocab = load_pkl("../models/vocab")
            Classifier._line_model = load_model("../models/line__final_100N_5B_8.h5")
            Classifier._length_model = load_model("../models/length__final_100N_5B_4.h5")
            Classifier._lemmatizer = nltk.stem.WordNetLemmatizer()
            # logger.log("Loaded models!")
            Classifier.loaded = True

    @staticmethod
    def classify(comms):
        """
        :type comms: raw commentary 'desc'
        :rtype: (line class, confidence), (length class, confidence)
        """

        Classifier.load()
        tokens = text_to_word_sequence(comms)
        tokens_sw = [w for w in tokens if w in Classifier._vocab]

        # Don't even try and predict for this type of ball
        if len(tokens_sw) <= 1:
            return None

        lemmatized = Classifier._lemmatize_text(tokens_sw)
        xLength = Classifier._ngramsInText(lemmatized, Classifier._length_ngrams)
        xLine = Classifier._ngramsInText(lemmatized, Classifier._line_ngrams)

        line = Classifier._line_model.predict(np.array([xLine, ]))
        length = Classifier._length_model.predict(np.array([xLength, ]))

        return (line.argmax(axis=1)[0], max(line[0])), (length.argmax(axis=1)[0], max(length[0]))

    @staticmethod
    def _lemmatize_text(text):
        lemmas = []
        for w, tag in nltk.pos_tag(text):
            wnTag = tag[0].lower()
            wnTag = wnTag if wnTag in ['a', 'r', 'n', 'v'] else None
            lemmas.append(Classifier._lemmatizer.lemmatize(w, wnTag) if wnTag else w)
        return " ".join(lemmas)

    @staticmethod
    def _ngramsInText(text, ngramFeatures):
        ngramPresence = dict()
        for ngram in ngramFeatures:
            ngramSplit = ngram.split(' ')
            ngramPresence[ngram] = int(tuple(ngramSplit) in set(nltk.ngrams(text.split(' '), len(ngramSplit))))
        return pd.Series(ngramPresence).values


if __name__ == "__main__":
    while True:
        example = input()
        print(Classifier.classify(example))
