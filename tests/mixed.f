C     Test combining comments, continuations and labels
      PROGRAM MIXED
      INTEGER A, B,
C     This comment inside a continuation should NOT be treated as continuation
     + C
20    A = 1 +
     + 2 +
* Comment mid-continuation
     + 3
      END