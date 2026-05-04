C     Testa operadores lógicos .OR. e .NOT., e o literal .FALSE.
C     Esperado: imprime 1 duas vezes (.TRUE. OR .FALSE. = T; NOT .FALSE. = T)
      PROGRAM LOGOPS
      LOGICAL A, B
      A = .TRUE.
      B = .FALSE.
      IF (A .OR. B) THEN
          PRINT *, 1
      ENDIF
      IF (.NOT. B) THEN
          PRINT *, 1
      ENDIF
      END
