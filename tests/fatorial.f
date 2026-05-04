C     Calcula o fatorial de N usando um ciclo DO.
C     Entrada: inteiro positivo N (ex: 5)
C     Esperado: "Fatorial de 5 : 120"
      PROGRAM FATORIAL
      INTEGER N, I, FAT
      PRINT *, 'Introduza um numero inteiro positivo:'
      READ *, N
      FAT = 1
      DO 10 I = 1, N
          FAT = FAT * I
  10  CONTINUE
      PRINT *, 'Fatorial de ', N, ': ', FAT
      END
