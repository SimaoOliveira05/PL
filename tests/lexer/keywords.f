      PROGRAM TEST
      INTEGER A
      REAL B
      LOGICAL C
      CHARACTER D
      IF (A) THEN
      ELSE
      ENDIF
      DO 10 A = 1, 2
  10  CONTINUE
      GOTO 10
      READ *, A
      PRINT *, A
      CALL FOO
      RETURN
      END

      SUBROUTINE FOO
      END

      INTEGER FUNCTION BAR(X)
      INTEGER X
      RETURN
      END
