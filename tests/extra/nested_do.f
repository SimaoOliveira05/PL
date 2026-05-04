C     Testa ciclos DO aninhados (3x3 iterações, acumula S).
C     Esperado: imprime 9
      PROGRAM NESTDO
      INTEGER I, J, S
      S = 0
      DO 20 I = 1, 3
          DO 10 J = 1, 3
              S = S + 1
  10      CONTINUE
  20  CONTINUE
      PRINT *, S
      END
