# -*- coding: utf-8 -*-

import numpy as np
from sklearn.preprocessing import normalize
from collections import Counter
from collections import defaultdict
import math
import scipy as sp
from scipy.sparse import csr_matrix
from sklearn.metrics import pairwise_distances

# KoNLPy
from konlpy.tag import Komoran

# Crawling sentences
from selenium import webdriver

# TTS
from gtts import gTTS
import win32com.client

########################################### Source Code ####################################
# author : 김현중
# git address : https://github.com/lovit/textrank/
# 위 주소의 textRank 패키지 코드를 사용했습니다.

### Rank Function
def pagerank(x, df = 0.85, max_iter = 30, bias = None):
    """
    Arguments
    ---------
    x : scipy.sparse.csr_matrix
        shape = (n vertex, n vertex)
    df : float
        Damping factor, 0 < df < 1
    max_iter : int
        Maximum number of iteration
    bias : numpy.ndarray or None
        If None, equal bias
    Returns
    -------
    R : numpy.ndarray
        PageRank vector. shape = (n vertex, 1)
    """

    assert 0 < df < 1

    # initialize
    A = normalize(x, axis=0, norm='l1')
    R = np.ones(A.shape[0]).reshape(-1,1)

    # check bias
    if bias is None:
        bias = (1 - df) * np.ones(A.shape[0]).reshape(-1,1)
    else:
        bias = bias.reshape(-1,1)
        bias = A.shape[0] * bias / bias.sum()
        assert bias.shape[0] == A.shape[0]
        bias = (1 - df) * bias

    # iteration
    for _ in range(max_iter):
        R = df * (A * R) + bias

    return R

### Senteces Function
def sent_graph(sents, tokenize=None, min_count=2, min_sim=0.3,
    similarity=None, vocab_to_idx=None, verbose=False):
    """
    Arguments
    ---------
    sents : list of str
        Sentence list
    tokenize : callable
        tokenize(sent) return list of str
    min_count : int
        Minimum term frequency
    min_sim : float
        Minimum similarity between sentences
    similarity : callable or str
        similarity(s1, s2) returns float
        s1 and s2 are list of str.
        available similarity = [callable, 'cosine', 'textrank']
    vocab_to_idx : dict
        Vocabulary to index mapper.
        If None, this function scan vocabulary first.
    verbose : Boolean
        If True, verbose mode on
    Returns
    -------
    sentence similarity graph : scipy.sparse.csr_matrix
        shape = (n sents, n sents)
    """

    if vocab_to_idx is None:
        idx_to_vocab, vocab_to_idx = scan_vocabulary(sents, tokenize, min_count)
    else:
        idx_to_vocab = [vocab for vocab, _ in sorted(vocab_to_idx.items(), key=lambda x:x[1])]

    x = vectorize_sents(sents, tokenize, vocab_to_idx)
    if similarity == 'cosine':
        x = numpy_cosine_similarity_matrix(x, min_sim, verbose, batch_size=1000)
    else:
        x = numpy_textrank_similarity_matrix(x, min_sim, verbose, batch_size=1000)
    return x

def vectorize_sents(sents, tokenize, vocab_to_idx):
    rows, cols, data = [], [], []
    for i, sent in enumerate(sents):
        counter = Counter(tokenize(sent))
        for token, count in counter.items():
            j = vocab_to_idx.get(token, -1)
            if j == -1:
                continue
            rows.append(i)
            cols.append(j)
            data.append(count)
    n_rows = len(sents)
    n_cols = len(vocab_to_idx)
    return csr_matrix((data, (rows, cols)), shape=(n_rows, n_cols))

def numpy_cosine_similarity_matrix(x, min_sim=0.3, verbose=True, batch_size=1000):
    n_rows = x.shape[0]
    mat = []
    for bidx in range(math.ceil(n_rows / batch_size)):
        b = int(bidx * batch_size)
        e = min(n_rows, int((bidx+1) * batch_size))
        psim = 1 - pairwise_distances(x[b:e], x, metric='cosine')
        rows, cols = np.where(psim >= min_sim)
        data = psim[rows, cols]
        mat.append(csr_matrix((data, (rows, cols)), shape=(e-b, n_rows)))
        if verbose:
            print('\rcalculating cosine sentence similarity {} / {}'.format(b, n_rows), end='')
    mat = sp.sparse.vstack(mat)
    if verbose:
        print('\rcalculating cosine sentence similarity was done with {} sents'.format(n_rows))
    return mat

def numpy_textrank_similarity_matrix(x, min_sim=0.3, verbose=True, min_length=1, batch_size=1000):
    n_rows, n_cols = x.shape

    # Boolean matrix
    rows, cols = x.nonzero()
    data = np.ones(rows.shape[0])
    z = csr_matrix((data, (rows, cols)), shape=(n_rows, n_cols))

    # Inverse sentence length
    size = np.asarray(x.sum(axis=1)).reshape(-1)
    size[np.where(size <= min_length)] = 10000
    size = np.log(size)

    mat = []
    for bidx in range(math.ceil(n_rows / batch_size)):

        # slicing
        b = int(bidx * batch_size)
        e = min(n_rows, int((bidx+1) * batch_size))

        # dot product
        inner = z[b:e,:] * z.transpose()

        # sentence len[i,j] = size[i] + size[j]
        norm = size[b:e].reshape(-1,1) + size.reshape(1,-1)
        norm = norm ** (-1)
        norm[np.where(norm == np.inf)] = 0

        # normalize
        sim = inner.multiply(norm).tocsr()
        rows, cols = (sim >= min_sim).nonzero()
        data = np.asarray(sim[rows, cols]).reshape(-1)

        # append
        mat.append(csr_matrix((data, (rows, cols)), shape=(e-b, n_rows)))

        if verbose:
            print('\rcalculating textrank sentence similarity {} / {}'.format(b, n_rows), end='')

    mat = sp.sparse.vstack(mat)
    if verbose:
        print('\rcalculating textrank sentence similarity was done with {} sents'.format(n_rows))

    return mat

def graph_with_python_sim(tokens, verbose, similarity, min_sim):
    if similarity == 'cosine':
        similarity = cosine_sent_sim
    elif callable(similarity):
        similarity = similarity
    else:
        similarity = textrank_sent_sim

    rows, cols, data = [], [], []
    n_sents = len(tokens)
    for i, tokens_i in enumerate(tokens):
        if verbose and i % 1000 == 0:
            print('\rconstructing sentence graph {} / {} ...'.format(i, n_sents), end='')
        for j, tokens_j in enumerate(tokens):
            if i >= j:
                continue
            sim = similarity(tokens_i, tokens_j)
            if sim < min_sim:
                continue
            rows.append(i)
            cols.append(j)
            data.append(sim)
    if verbose:
        print('\rconstructing sentence graph was constructed from {} sents'.format(n_sents))
    return csr_matrix((data, (rows, cols)), shape=(n_sents, n_sents))

def textrank_sent_sim(s1, s2):
    """
    Arguments
    ---------
    s1, s2 : list of str
        Tokenized sentences
    Returns
    -------
    Sentence similarity : float
        Non-negative number
    """
    n1 = len(s1)
    n2 = len(s2)
    if (n1 <= 1) or (n2 <= 1):
        return 0
    common = len(set(s1).intersection(set(s2)))
    base = math.log(n1) + math.log(n2)
    return common / base

def cosine_sent_sim(s1, s2):
    """
    Arguments
    ---------
    s1, s2 : list of str
        Tokenized sentences
    Returns
    -------
    Sentence similarity : float
        Non-negative number
    """
    if (not s1) or (not s2):
        return 0

    s1 = Counter(s1)
    s2 = Counter(s2)
    norm1 = math.sqrt(sum(v ** 2 for v in s1.values()))
    norm2 = math.sqrt(sum(v ** 2 for v in s2.values()))
    prod = 0
    for k, v in s1.items():
        prod += v * s2.get(k, 0)
    return prod / (norm1 * norm2)

### Summarizer Function
class KeywordSummarizer:
    """
    Arguments
    ---------
    sents : list of str
        Sentence list
    tokenize : callable
        Tokenize function: tokenize(str) = list of str
    min_count : int
        Minumum frequency of words will be used to construct sentence graph
    window : int
        Word cooccurrence window size. Default is -1.
        '-1' means there is cooccurrence between two words if the words occur in a sentence
    min_cooccurrence : int
        Minimum cooccurrence frequency of two words
    vocab_to_idx : dict or None
        Vocabulary to index mapper
    df : float
        PageRank damping factor
    max_iter : int
        Number of PageRank iterations
    verbose : Boolean
        If True, it shows training progress
    """
    def __init__(self, sents=None, tokenize=None, min_count=2,
        window=-1, min_cooccurrence=2, vocab_to_idx=None,
        df=0.85, max_iter=30, verbose=False):

        self.tokenize = tokenize
        self.min_count = min_count
        self.window = window
        self.min_cooccurrence = min_cooccurrence
        self.vocab_to_idx = vocab_to_idx
        self.df = df
        self.max_iter = max_iter
        self.verbose = verbose

        if sents is not None:
            self.train_textrank(sents)

    def train_textrank(self, sents, bias=None):
        """
        Arguments
        ---------
        sents : list of str
            Sentence list
        bias : None or numpy.ndarray
            PageRank bias term
        Returns
        -------
        None
        """

        g, self.idx_to_vocab = word_graph(sents,
            self.tokenize, self.min_count,self.window,
            self.min_cooccurrence, self.vocab_to_idx, self.verbose)
        self.R = pagerank(g, self.df, self.max_iter, bias).reshape(-1)
        if self.verbose:
            print('trained TextRank. n words = {}'.format(self.R.shape[0]))

    def keywords(self, topk=30):
        """
        Arguments
        ---------
        topk : int
            Number of keywords selected from TextRank
        Returns
        -------
        keywords : list of tuple
            Each tuple stands for (word, rank)
        """
        if not hasattr(self, 'R'):
            raise RuntimeError('Train textrank first or use summarize function')
        idxs = self.R.argsort()[-topk:]
        keywords = [(self.idx_to_vocab[idx], self.R[idx]) for idx in reversed(idxs)]
        return keywords

    def summarize(self, sents, topk=30):
        """
        Arguments
        ---------
        sents : list of str
            Sentence list
        topk : int
            Number of keywords selected from TextRank
        Returns
        -------
        keywords : list of tuple
            Each tuple stands for (word, rank)
        """
        self.train_textrank(sents)
        return self.keywords(topk)


class KeysentenceSummarizer:
    """
    Arguments
    ---------
    sents : list of str
        Sentence list
    tokenize : callable
        Tokenize function: tokenize(str) = list of str
    min_count : int
        Minumum frequency of words will be used to construct sentence graph
    min_sim : float
        Minimum similarity between sentences in sentence graph
    similarity : str
        available similarity = ['cosine', 'textrank']
    vocab_to_idx : dict or None
        Vocabulary to index mapper
    df : float
        PageRank damping factor
    max_iter : int
        Number of PageRank iterations
    verbose : Boolean
        If True, it shows training progress
    """
    def __init__(self, sents=None, tokenize=None, min_count=2,
        min_sim=0.3, similarity=None, vocab_to_idx=None,
        df=0.85, max_iter=30, verbose=False):

        self.tokenize = tokenize
        self.min_count = min_count
        self.min_sim = min_sim
        self.similarity = similarity
        self.vocab_to_idx = vocab_to_idx
        self.df = df
        self.max_iter = max_iter
        self.verbose = verbose

        if sents is not None:
            self.train_textrank(sents)

    def train_textrank(self, sents, bias=None):
        """
        Arguments
        ---------
        sents : list of str
            Sentence list
        bias : None or numpy.ndarray
            PageRank bias term
            Shape must be (n_sents,)
        Returns
        -------
        None
        """
        g = sent_graph(sents, self.tokenize, self.min_count,
            self.min_sim, self.similarity, self.vocab_to_idx, self.verbose)
        self.R = pagerank(g, self.df, self.max_iter, bias).reshape(-1)
        if self.verbose:
            print('trained TextRank. n sentences = {}'.format(self.R.shape[0]))

    def summarize(self, sents, topk=30, bias=None):
        """
        Arguments
        ---------
        sents : list of str
            Sentence list
        topk : int
            Number of key-sentences to be selected.
        bias : None or numpy.ndarray
            PageRank bias term
            Shape must be (n_sents,)
        Returns
        -------
        keysents : list of tuple
            Each tuple stands for (sentence index, rank, sentence)
        Usage
        -----
        #    >>> from textrank import KeysentenceSummarizer
        #    >>> summarizer = KeysentenceSummarizer(tokenize = tokenizer, min_sim = 0.5)
        #    >>> keysents = summarizer.summarize(texts, topk=30)
        """
        n_sents = len(sents)
        if isinstance(bias, np.ndarray):
            if bias.shape != (n_sents,):
                raise ValueError('The shape of bias must be (n_sents,) but {}'.format(bias.shape))
        elif bias is not None:
            raise ValueError('The type of bias must be None or numpy.ndarray but the type is {}'.format(type(bias)))

        self.train_textrank(sents, bias)
        idxs = self.R.argsort()[-topk:]
        keysents = [(idx, self.R[idx], sents[idx]) for idx in reversed(idxs)]
        return keysents

### Utility Function
def scan_vocabulary(sents, tokenize=None, min_count=2):
    """
    Arguments
    ---------
    sents : list of str
        Sentence list
    tokenize : callable
        tokenize(str) returns list of str
    min_count : int
        Minumum term frequency
    Returns
    -------
    idx_to_vocab : list of str
        Vocabulary list
    vocab_to_idx : dict
        Vocabulary to index mapper.
    """
    counter = Counter(w for sent in sents for w in tokenize(sent))
    counter = {w:c for w,c in counter.items() if c >= min_count}
    idx_to_vocab = [w for w, _ in sorted(counter.items(), key=lambda x:-x[1])]
    vocab_to_idx = {vocab:idx for idx, vocab in enumerate(idx_to_vocab)}
    return idx_to_vocab, vocab_to_idx

def tokenize_sents(sents, tokenize):
    """
    Arguments
    ---------
    sents : list of str
        Sentence list
    tokenize : callable
        tokenize(sent) returns list of str (word sequence)
    Returns
    -------
    tokenized sentence list : list of list of str
    """
    return [tokenize(sent) for sent in sents]

def vectorize(tokens, vocab_to_idx):
    """
    Arguments
    ---------
    tokens : list of list of str
        Tokenzed sentence list
    vocab_to_idx : dict
        Vocabulary to index mapper
    Returns
    -------
    sentence bow : scipy.sparse.csr_matrix
        shape = (n_sents, n_terms)
    """
    rows, cols, data = [], [], []
    for i, tokens_i in enumerate(tokens):
        for t, c in Counter(tokens_i).items():
            j = vocab_to_idx.get(t, -1)
            if j == -1:
                continue
            rows.append(i)
            cols.append(j)
            data.append(c)
    n_sents = len(tokens)
    n_terms = len(vocab_to_idx)
    x = csr_matrix((data, (rows, cols)), shape=(n_sents, n_terms))
    return x


### Word Function
def word_graph(sents, tokenize=None, min_count=2, window=2,
    min_cooccurrence=2, vocab_to_idx=None, verbose=False):
    """
    Arguments
    ---------
    sents : list of str
        Sentence list
    tokenize : callable
        tokenize(str) returns list of str
    min_count : int
        Minumum term frequency
    window : int
        Co-occurrence window size
    min_cooccurrence : int
        Minimum cooccurrence frequency
    vocab_to_idx : dict
        Vocabulary to index mapper.
        If None, this function scan vocabulary first.
    verbose : Boolean
        If True, verbose mode on
    Returns
    -------
    co-occurrence word graph : scipy.sparse.csr_matrix
    idx_to_vocab : list of str
        Word list corresponding row and column
    """
    if vocab_to_idx is None:
        idx_to_vocab, vocab_to_idx = scan_vocabulary(sents, tokenize, min_count)
    else:
        idx_to_vocab = [vocab for vocab, _ in sorted(vocab_to_idx.items(), key=lambda x:x[1])]

    tokens = tokenize_sents(sents, tokenize)
    g = cooccurrence(tokens, vocab_to_idx, window, min_cooccurrence, verbose)
    return g, idx_to_vocab

def cooccurrence(tokens, vocab_to_idx, window=2, min_cooccurrence=2, verbose=False):
    """
    Arguments
    ---------
    tokens : list of list of str
        Tokenized sentence list
    vocab_to_idx : dict
        Vocabulary to index mapper
    window : int
        Co-occurrence window size
    min_cooccurrence : int
        Minimum cooccurrence frequency
    verbose : Boolean
        If True, verbose mode on
    Returns
    -------
    co-occurrence matrix : scipy.sparse.csr_matrix
        shape = (n_vocabs, n_vocabs)
    """
    counter = defaultdict(int)
    for s, tokens_i in enumerate(tokens):
        if verbose and s % 1000 == 0:
            print('\rword cooccurrence counting {}'.format(s), end='')
        vocabs = [vocab_to_idx[w] for w in tokens_i if w in vocab_to_idx]
        n = len(vocabs)
        for i, v in enumerate(vocabs):
            if window <= 0:
                b, e = 0, n
            else:
                b = max(0, i - window)
                e = min(i + window, n)
            for j in range(b, e):
                if i == j:
                    continue
                counter[(v, vocabs[j])] += 1
                counter[(vocabs[j], v)] += 1
    counter = {k:v for k,v in counter.items() if v >= min_cooccurrence}
    n_vocabs = len(vocab_to_idx)
    if verbose:
        print('\rword cooccurrence counting from {} sents was done'.format(s+1))
    return dict_to_mat(counter, n_vocabs, n_vocabs)

def dict_to_mat(d, n_rows, n_cols):
    """
    Arguments
    ---------
    d : dict
        key : (i,j) tuple
        value : float value
    Returns
    -------
    scipy.sparse.csr_matrix
    """
    rows, cols, data = [], [], []
    for (i, j), v in d.items():
        rows.append(i)
        cols.append(j)
        data.append(v)
    return csr_matrix((data, (rows, cols)), shape=(n_rows, n_cols))


###############################################################################################
# author : minji Kwon (minmin0916@khu.ac.kr)
### main
# tokenize function
komoran = Komoran()
def komoran_tokenize(sent):
    words = komoran.pos(sent, join=True)
    words = [w for w in words if ('/NN' in w or '/XR' in w or '/VA' in w or '/VV' in w)]
    return words

### url에서 제목과 본문만 list of string 형태로 추출
# crawling class
class crawling_sents:
    def __init__(self):
        self.url = 'https://news.naver.com/main/read.nhn?mode=LSD&mid=shm&sid1=102&oid=025&aid=0003013614'
        self.driver = webdriver.Chrome('C:/Users/Gwon/Downloads/chromedriver_win32/chromedriver.exe')

    def crawling_sents(self):
        f = open('result1.txt', 'w', encoding='utf-8')
        self.driver.get(self.url)

        title = self.driver.find_element_by_id("articleTitle").text
        article = self.driver.find_element_by_id("articleBodyContents").text
        article = article.replace('\n', '')
        article = article.replace(']', ']\n')
        article = article.replace('.', '.\n')
        f.write(title + "\n")
        f.writelines(article)

        f.close()
        self.driver.close()

crawl_sents = crawling_sents()
crawl_sents.crawling_sents()

# 크롤링한 text list of string (sents)에 넣어주기
file = open('D:/ProgramFile/KoNLPy_Project/result1.txt', 'rt', encoding='UTF8')
sents = file.readlines()
file.close()

#print(sents)

keyword_extractor = KeywordSummarizer(
    tokenize=komoran_tokenize,
    window=-1,
    verbose=False
)
keywords = keyword_extractor.summarize(sents, topk=30)

summarizer = KeysentenceSummarizer(tokenize = komoran_tokenize, min_sim = 0.3)
keysents = summarizer.summarize(sents, topk=3)

#print(keywords)
#print(keysents)

# Preprocess keywords and key sentences for TTS

keyword_tts = ""
keysents_tts = ""

i = 0

for word in keywords:
    if i == 10:
        break

    x, y = word

    # 특정 문자 제거
    for char in x:
        if char in "/NNG":
            x = x.replace(char, " ")
        elif char in "/NNB":
            x = x.replace(char, " ")
        elif char in "/NNP":
            x = x.replace(char, " ")
        elif char in "/VV":
            x = x.replace(char, " ")
    
    # 한 글자 단어 제거
    #print(x)
    if len(x.encode("utf-8")) > 7:
        keyword_tts = keyword_tts + x
        i = i + 1



print("키워드 : " + keyword_tts)

for line in keysents:
    x, y, z = line
    keysents_tts = keysents_tts + z

print("주요 문장 : \n" + keysents_tts)

# Window Speech API(SAPI)
tts = win32com.client.Dispatch("SAPI.SpVoice")
tts.Speak("키워드는 다음과 같다")
tts.Speak(keyword_tts)
tts.Speak("주요 문장은 다음과 같다")
tts.Speak(keysents_tts)
