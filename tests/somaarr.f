C     Lê 5 inteiros para um array e calcula a soma com DO.
C     Testa READ e acesso a array dentro de um ciclo.
C     Entrada: 5 inteiros (ex: 1 2 3 4 5)
C     Esperado: "A soma dos numeros e: 15"
      PROGRAM SOMAARR
      INTEGER NUMS(5)
      INTEGER I, SOMA
      SOMA = 0
      PRINT *, 'Introduza 5 numeros inteiros:'
      DO 30 I = 1, 5
          READ *, NUMS(I)
          SOMA = SOMA + NUMS(I)
  30  CONTINUE
      PRINT *, 'A soma dos numeros e: ', SOMA
      END
