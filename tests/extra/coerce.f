C     Testa coerção implícita INTEGER -> REAL numa expressão mista.
C     Esperado: imprime 4.5 (3 + 1.5, com 3 convertido para REAL)
      PROGRAM COERCE
      REAL X
      INTEGER N
      N = 3
      X = N + 1.5
      PRINT *, X
      END
