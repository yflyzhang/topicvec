import getopt
import glob
import sys
import os.path
from utils import *
import numpy as np
#import pdb

getAbsentWords = False
modelFiles = [ "./GoogleNews-vectors-negative300.bin", "./29291-500-EM.vec", "./100000-500-BLKEM.vec",
                "./wordvecs/vec_520_forest", "./wiki-glove.vec2.txt" ]

isModelsBinary = [ True, False, False, False, False ]
modelID = -1

# default is current directory
simTestsetDir = "./testsets/ws/"
# if set to [], run all testsets
simTestsetNames = [ "ws353_similarity", "ws353_relatedness", "bruni_men", "radinsky_mturk", "luong_rare", "simlex_999a" ]
anaTestsetDir = "./testsets/analogy/"
# if set to [], run all testsets
anaTestsetNames = [] #[ "google", "msr" ]

unigramFilename = "top1grams-wiki.txt"
vecNormalize = True
loadwordCutPoint = -1
testwordCutPoint = -1
absentFilename = ""
extraWordFilename = ""
# default is in text format
isModelBinary = False
modelFile = None
# precompute the cosine similarity matrix of all pairs of words
# need W*W*4 bytes of RAM
precomputeCosine = True

def usage():
    print """Usage: evaluate.py [ -m model_file -i builtin_model_id -e extra_word_file -a absent_file -u unigram_file ... ]
Options:
  -m:    Path to the model file, a ".vec" or ".bin" file for word2vec
  -b:    Model file is in binary format (default: text)
  -d:    A directory containing the test files
  -f:    A list of test files in the specified directory
  -i:    Builtin model ID for the benchmark. Range: 1 (word2vec),
         2 (PSD 29291 words), 3 (block PSD 100000 words), 4 (forest), 5(glove)
  -P:    Do not precompute cosine matrix. When the vocab is huge, 
         it's necessary to disable computing this matrix.
  -u:    Unigram file, for missing word check.
         Its presence will enable checking of what words are missing
         from the vocabulary and the model
  -c:    Loaded Model vocabulary cut point. Load top x words from the model file
  -t:    Vocabulary cut point for the test sets. All words in the test sets
         whose IDs are below it will be picked out
  -e:    Extra word file. Words in this list will be loaded anyway
  -a:    Absent file. Words below the cut point will be saved there"""

try:
    opts, args = getopt.getopt(sys.argv[1:],"m:bd:f:i:Pu:c:t:e:a:h")
    if len(args) != 0:
        raise getopt.GetoptError("")
    for opt, arg in opts:
        if opt == '-m':
            modelID = -1
            modelFile = arg
        if opt == '-b':
            isModelBinary = bool(arg)
        if opt == '-d':
            testsetDir = arg
        if opt == '-f':
            testsetNames = filter( lambda x: x, arg.split(",") )
        if opt == '-i':
            modelID = int(arg)
        if opt == '-P':
            precomputeCosine = False
        if opt == '-u':
            # unigram file is used to get a full list of words,
            # and also to sort the absent words by their frequencies
            unigramFilename = arg
        if opt == '-c':
            loadwordCutPoint = int(arg)
        if opt == '-t':
            testwordCutPoint = int(arg)
        if opt == '-e':
            extraWordFilename = arg
        if opt == '-a':
            getAbsentWords = True
            absentFilename = arg
        if opt == '-h':
            usage()
            sys.exit(0)

    if getAbsentWords and not unigramFilename:
        print "ERR: -u (Unigram file) has to be specified to get absent words"
        sys.exit(2)
    # "-" means output to console instead of a file
    if absentFilename == "-":
        absentFilename = ""

except getopt.GetoptError:
   usage()
   sys.exit(2)

if modelID > 0:
    modelFile = modelFiles[ modelID - 1 ]
    isModelBinary = isModelsBinary[ modelID - 1 ]

if modelFile is None:
    usage()
    sys.exit(2)
    
vocab = {}
if unigramFilename:
    vocab = loadUnigramFile(unigramFilename)

if extraWordFilename:
    extraWords = loadExtraWordFile(extraWordFilename)
else:
    extraWords = {}

if loadwordCutPoint > 0:
    print "Load top %d words" %(loadwordCutPoint)

if isModelBinary:
    V, vocab2, word2dim, skippedWords = load_embeddings_bin( modelFile, loadwordCutPoint, extraWords )
else:
    V, vocab2, word2dim, skippedWords =     load_embeddings( modelFile, loadwordCutPoint, extraWords )

# if evalVecExpectation = True, compute the expectation of all embeddings
evalVecExpectation = False
if evalVecExpectation and unigramFilename:
    expVec = np.zeros( len(V[0]) )
    expVecNorm1 = 0
    expVecNorm2 = 0
    totalWords = 0
    expWords = 0
    accumProb = 0.0
    for w in vocab2:
        totalWords += 1
        if w in vocab:
            expVec += V[ word2dim[w] ] * vocab[w][2]
            expVecNorm1 += norm1( V[ word2dim[w] ] ) * vocab[w][2]
            expVecNorm2 += normF( V[ word2dim[w] ] ) * vocab[w][2]
            expWords += 1
            accumProb += vocab[w][2]

    expVec /= accumProb
    expVecNorm1 /= accumProb
    expVecNorm2 /= accumProb
    print "totally %d words, %d words in E[v]. |E[v]|: %.3f/%.3f, E[|v|]: %.3f/%.3f" %( totalWords, expWords,
                                                                norm1(expVec), normF(expVec), expVecNorm1, expVecNorm2 )

model = VecModel(V, vocab2, word2dim, vecNormalize=vecNormalize)
if precomputeCosine:
    model.precompute_cosine()

simTestsets = loadTestsets(loadSimTestset, simTestsetDir, simTestsetNames)
anaTestsets = loadTestsets(loadAnaTestset, anaTestsetDir, anaTestsetNames)

spearmanCoeff, absentModelID2Word1, absentVocabWords1, cutVocabWords1 = \
            evaluate_sim( model, simTestsets, simTestsetNames, getAbsentWords, vocab, testwordCutPoint )

anaScores,     absentModelID2Word2, absentVocabWords2, cutVocabWords2 = \
            evaluate_ana( model, anaTestsets, anaTestsetNames, getAbsentWords, vocab, testwordCutPoint )

if getAbsentWords:
    # merge the two sets of absent words
    absentModelID2Word1.update(absentModelID2Word2)
    absentModelWordIDs = sorted( absentModelID2Word1.keys() )
    absentModelWords = [ absentModelID2Word1[i] for i in absentModelWordIDs ]

    absentVocabWords1.update(absentVocabWords2)
    absentVocabWords = sorted( absentVocabWords1.keys() )

    cutVocabWords1.update(cutVocabWords2)
    # sort by ID in ascending, so that most frequent words (smaller IDs) first
    cutVocabWords = sorted( cutVocabWords1.keys(), key=lambda w: vocab[w][0] )

    print "\n%d words absent from the model:" %len(absentModelWordIDs)
    print "ID:"
    print ",".join( map( lambda i: str(i), absentModelWordIDs) )
    print "\nWords:"
    print ",".join(absentModelWords)

    if len(absentVocabWords) > 0:
        print "\n%d words absent from the vocab:" %len(absentVocabWords)
        print "\n".join(absentVocabWords)

    print

    if absentFilename and len(cutVocabWords):
        ABS = open(absentFilename, "w")
        for w in cutVocabWords:
            ABS.write( "%s\t%d\n" %( w, vocab[w][0] ) )
        ABS.close()
        print "%d words saved to %s" %( len(cutVocabWords), absentFilename )
