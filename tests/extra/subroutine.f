C     Testa SUBROUTINE com CALL e passagem de argumento.
C     Esperado: imprime 7
      PROGRAM SUBTEST
      INTEGER X
      X = 7
      CALL PRINTVAL(X)
      END

      SUBROUTINE PRINTVAL(N)
      INTEGER N
      PRINT *, N
      RETURN
      END
