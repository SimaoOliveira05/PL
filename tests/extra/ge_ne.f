C     Testa operadores relacionais .GE., .NE. e .LT.
C     Esperado: imprime 1, 1 (5>=3 e 5/=3 são verdadeiros; 5<3 é falso, não imprime)
      PROGRAM GENEPROG
      INTEGER A
      A = 5
      IF (A .GE. 3) THEN
          PRINT *, 1
      ENDIF
      IF (A .NE. 3) THEN
          PRINT *, 1
      ENDIF
      IF (A .LT. 3) THEN
          PRINT *, 0
      ENDIF
      END
