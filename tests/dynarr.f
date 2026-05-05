      PROGRAM DYNARR
      INTEGER A(5), I
      CALL FILL(A, 5)
      DO 10 I = 1, 5
          PRINT *, A(I)
  10  CONTINUE
      END

      SUBROUTINE FILL(A, N)
      INTEGER N, A(N), I
      DO 10 I = 1, N
          A(I) = I * 10
  10  CONTINUE
      END
