ANALYZER_VERSION = 1

# Minimum words a sentence must have to be considered for redundancy checks
MIN_WORDS_PER_SENTENCE = 4

# Threshold for cosine similarity to be considered a near-duplicate
SIMILARITY_THRESHOLD = 0.90

# Maximum number of sentences to embed per prompt to bound processing time and memory
MAX_SENTENCES_EMBEDDED = 200

# Minimum requests a template group must have before we flag verbose outliers
VERBOSE_GROUP_MIN_SIZE = 3

# Severity threshold for estimated wasted tokens relative to total input tokens (Redundant content)
REDUNDANCY_SEVERITY_HIGH_PCT = 0.30
REDUNDANCY_SEVERITY_MEDIUM_PCT = 0.10

# Severity threshold for input tokens vs template minimum tokens (Verbose template)
VERBOSE_SEVERITY_HIGH_RATIO = 5.0
VERBOSE_SEVERITY_MEDIUM_RATIO = 3.0

# Thresholds for repeated whitespace / exact words (Repeated content)
REPEATED_BLANK_LINES = 5
REPEATED_SPACES = 20
REPEATED_WORDS = 4
