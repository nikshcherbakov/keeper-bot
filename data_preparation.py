# This script gets the data ready for future work with ML model
from pymorphy2 import MorphAnalyzer
import nltk
import numpy as np
import re
import pandas as pd


DATA_CATEGORIES = {
    'communal_data.txt': 'COMMUNAL',
    'food_data.txt': 'FOOD',
    'health_data.txt': 'HEALTH',
    'transport_data.txt': 'TRANSPORT',
    'entertainment_data.txt': 'ENTERTAINMENT'
}


''' The function finds sentences and word combinations in the text by looking for the verbs'''


def get_docs_by_verbs(text, min_len=1, max_len=10):

    def check_delimiters(txt):
        delimiters = ',().-\n\t\r'
        for delimiter in delimiters:
            if delimiter in txt:
                return True
        return False

    docs = []
    m = MorphAnalyzer()
    words = re.split(r' - | ', text)

    doc = []
    doc_len = np.random.randint(low=min_len, high=max_len)
    is_being_added = False
    for i, word in enumerate(words):
        # looking for verbs
        try:
            if 'VERB' in m.parse(word)[0].tag or 'NOUN' in m.parse(word)[0].tag or is_being_added:
                if len(doc) < doc_len:
                    if not check_delimiters(word):
                        doc.append(word)
                        is_being_added = True
                    else:
                        if doc:
                            docs.append(doc)
                            doc = []

                        is_being_added = False
                        doc_len = np.random.randint(low=min_len, high=max_len)
                else:
                    docs.append(doc)
                    doc = []
                    doc_len = np.random.randint(low=min_len, high=max_len)
                    is_being_added = False
        except KeyError:
            print(f'Inappropriate word: {word}')

    return docs


'''This function just divides the text given into docs using random length'''


def divide_text_into_docs(text, min_len=1, max_len=10):
    sentences = [sentence for sentence in re.split(r', |[.] | - | – |\n', text)
                 if min_len <= len(sentence.split()) <= max_len]
    return sentences


''' This function cleans data to its future using in OHE '''


def clean_sentences(sentences, additional_stopwords=None):
    if additional_stopwords is None:
        additional_stopwords = []
    m = MorphAnalyzer()
    stop_words = nltk.corpus.stopwords.words('russian') + additional_stopwords
    sentences_clean = []

    # throw out all non-letter characters
    for sentence in sentences:
        words = re.findall(r"[а-яa-z'-]+", sentence.lower())
        normal_words = [m.parse(word)[0].normal_form for word in words]
        sentence_clean = ' '.join([normal_word for normal_word in normal_words if normal_word not in stop_words])
        sentences_clean.append(sentence_clean)

    return sentences_clean


''' This function returns pandas.DataFrame containing all the data from files in DATA_CATEGORIES '''


def get_data_clean():
    docs_df = pd.DataFrame()

    for file in DATA_CATEGORIES.keys():
        with open(file, encoding="utf-8") as inf:
            txt = inf.read()

        txt_divided = divide_text_into_docs(txt, 6, 12)

        sentences = clean_sentences(txt_divided)

        df = pd.DataFrame({
            'category': DATA_CATEGORIES[file],
            'text_clean': sentences
        })

        # adding df to docs_df
        docs_df = docs_df.append(df)

        # looking for most frequent words
        words_dict = {}
        words = " ".join(df["text_clean"]).split()

        for word in words:
            if word in words_dict:
                words_dict[word] += 1
            else:
                words_dict[word] = 1

        words_count = {k: v for k, v in sorted(words_dict.items(), key=lambda item: -item[1])}

        # printing data info by categories
        print(f'Category: {DATA_CATEGORIES[file]}')
        print(f'. Unique words: {len(set(words))}')
        print('. Most frequent words: {}'.format({k: v for k, v in list(words_count.items())[:15]}),
              end='\n' * 2)

    return docs_df.reset_index(drop=True)


if __name__ == '__main__':
    # saving dataframe as json file to its future usage in the model
    get_data_clean().to_json('data.json')
    get_data_clean().to_csv('data.csv')
    print('Data is saved to data.json')
