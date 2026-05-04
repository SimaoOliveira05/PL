C     Testa ciclo DO com passo diferente de 1 (step=2).
C     Esperado: imprime 0, 2, 4, 6, 8
      PROGRAM DOSTEP
      INTEGER I
      DO 10 I = 0, 8, 2
          PRINT *, I
  10  CONTINUE
      END
