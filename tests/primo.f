C     Verifica se NUM é primo usando GOTO como ciclo while.
C     Testa divisibilidade de 2 até NUM/2; usa variável LOGICAL.
C     Entrada: inteiro positivo (ex: 7)
C     Esperado (primo): "7 e um numero primo"
C     Esperado (não primo): "4 nao e um numero primo"
      PROGRAM PRIMO
      INTEGER NUM, I
      LOGICAL ISPRIM
      PRINT *, 'Introduza um numero inteiro positivo:'
      READ *, NUM
      ISPRIM = .TRUE.
      I = 2
  20  IF (I .LE. (NUM/2) .AND. ISPRIM) THEN
          IF (MOD(NUM, I) .EQ. 0) THEN
              ISPRIM = .FALSE.
          ENDIF
          I = I + 1
          GOTO 20
      ENDIF
      IF (ISPRIM) THEN
          PRINT *, NUM, ' e um numero primo'
      ELSE
          PRINT *, NUM, ' nao e um numero primo'
      ENDIF
      END
