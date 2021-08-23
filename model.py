# Model training and testing is written in this script
import pandas as pd
from sklearn.utils import shuffle
from sklearn import feature_extraction, model_selection, feature_selection, pipeline, naive_bayes, metrics
import numpy as np
from data_preparation import clean_sentences
import pickle

if __name__ == '__main__':
    df = pd.read_json('data.json')
    df = shuffle(df).reset_index(drop=True)

    # split dataset
    dtf_train, dtf_test = model_selection.train_test_split(df, test_size=0.3)

    # get target
    y_train = dtf_train["category"].values
    y_test = dtf_test["category"].values

    # Tf-Idf vectorizer
    vectorizer = feature_extraction.text.TfidfVectorizer(max_features=10000, ngram_range=(1, 2))

    corpus = dtf_train["text_clean"]

    # we are now going to prepare the data to work with the model
    vectorizer.fit(corpus)
    X_train = vectorizer.transform(corpus)
    dic_vocabulary = vectorizer.vocabulary_

    y = dtf_train["category"]
    X_names = vectorizer.get_feature_names()
    p_value_limit = 0.95
    dtf_features = pd.DataFrame()
    categories = np.unique(y)
    for cat in categories:
        chi2, p = feature_selection.chi2(X_train, y == cat)
        dtf_features = dtf_features.append(pd.DataFrame({"feature": X_names, "score": 1 - p, "y": cat}))
        dtf_features = dtf_features.sort_values(["y", "score"], ascending=[True, False])
        dtf_features = dtf_features[dtf_features["score"] > p_value_limit]
    X_names = dtf_features["feature"].unique().tolist()

    # data info
    for cat in categories:
        print("# {}:".format(cat))
        print("  . selected features:", len(dtf_features[dtf_features["y"] == cat]))
        print("  . top features:", ",".join(dtf_features[dtf_features["y"] == cat]["feature"].values[:10]))
        print(" ")

    # keep only the features with a certain p-value from the Chi-Square test and then refit vectorizer
    vectorizer = feature_extraction.text.TfidfVectorizer(vocabulary=X_names)
    vectorizer.fit(corpus)
    X_train = vectorizer.transform(corpus)
    dic_vocabulary = vectorizer.vocabulary_

    # looking for words consisting of zeros only
    X_train = X_train.todense()
    zero_rows_ind = np.where(~X_train.any(axis=1))[0]
    print(f'Zero rows indices: {zero_rows_ind}')
    print(f'Zero rows count: {len(zero_rows_ind)}')
    print(f'Overall number of rows: {X_train.shape[0]}', end='\n\n')

    # deleting all zero rows from X_train, X_test, y_train and y_test
    X_train = np.delete(X_train, zero_rows_ind, axis=0)
    y_train = np.delete(y_train, zero_rows_ind, axis=0)

    X_test = vectorizer.transform(dtf_test["text_clean"].values).todense()
    zero_rows_ind = np.where(~X_test.any(axis=1))[0]
    X_test = np.delete(X_test, zero_rows_ind, axis=0)
    y_test = np.delete(y_test, zero_rows_ind, axis=0)

    # Creating classifier
    classifier = naive_bayes.MultinomialNB()

    # pipeline
    model = pipeline.Pipeline([("vectorizer", vectorizer),
                               ("classifier", classifier)])
    # train classifier
    model["classifier"].fit(X_train, y_train)
    # test
    # X_test = dtf_test["text_clean"].values
    predicted = classifier.predict(X_test)
    predicted_prob = classifier.predict_proba(X_test)

    classes = np.unique(y_test)

    # Accuracy, Precision, Recall
    accuracy = metrics.accuracy_score(y_test, predicted)
    auc = metrics.roc_auc_score(y_test, predicted_prob,
                                multi_class="ovr")
    print("Accuracy:", round(accuracy, 2))
    print("Auc:", round(auc, 2))
    print("Detail:")
    print(metrics.classification_report(y_test, predicted))

    # testing model on new samples
    print('Testing the model on new samples')
    test_doc = ['Купил продукты в магазине', 'Справка в больнице', 'Устанновил газовую плиту', 'Белеберда',
                'Купил авиабилеты']

    print(f'Test documents: {test_doc}')

    txt_clean = clean_sentences(test_doc)
    print(f'Clean text: {txt_clean}')
    predicted_prob = model.predict_proba(txt_clean)
    print(f'Predicted probabilities={predicted_prob}')

    # doing predictions
    predictions = []
    threshold = 0.55

    for prob in predicted_prob:
        # we are looking for biggest probabilities that differ by no more than threshold percent
        predictions.append(categories[np.where(prob == max(prob))[0][0]] if max(prob) > threshold
                           else 'OTHER')

    print(f'Categories predicted: {predictions}')

    # saving model
    pickle.dump(model, open('model.pkl', 'wb'))

    print('Model is successfully saved to model.pkl')
