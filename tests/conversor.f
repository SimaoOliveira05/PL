C     Converte um número decimal para as bases 2 a 9.
C     Usa uma INTEGER FUNCTION (CONVRT) chamada em expressão.
C     CONVRT extrai dígitos na base B por divisões sucessivas (GOTO como while).
C     Entrada: inteiro decimal (ex: 10)
C     Esperado (para 10): BASE 2: 1010, BASE 8: 12, BASE 9: 11, etc.
      PROGRAM CONVERSOR
      INTEGER NUM, BASE, RESULT, CONVRT
      PRINT *, 'INTRODUZA UM NUMERO DECIMAL INTEIRO:'
      READ *, NUM
      DO 10 BASE = 2, 9
          RESULT = CONVRT(NUM, BASE)
          PRINT *, 'BASE ', BASE, ': ', RESULT
  10  CONTINUE
      END

      INTEGER FUNCTION CONVRT(N, B)
      INTEGER N, B, QUOT, REM, POT, VAL
      VAL = 0
      POT = 1
      QUOT = N
  20  IF (QUOT .GT. 0) THEN
          REM = MOD(QUOT, B)
          VAL = VAL + (REM * POT)
          QUOT = QUOT / B
          POT = POT * 10
          GOTO 20
      ENDIF
      CONVRT = VAL
      RETURN
      END
