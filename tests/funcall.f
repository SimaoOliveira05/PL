      PROGRAM FUNCALL
      INTEGER A, B, R
      INTEGER SOMA
      A = 3
      B = 7
      R = SOMA(A, B)
      PRINT *, R
      END

      INTEGER FUNCTION SOMA(X, Y)
      INTEGER X, Y
      SOMA = X + Y
      RETURN
      END
