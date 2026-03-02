'''
Encontre todos os números perfeitos entre dois números oferecidos pelo usúario. 
Um número perfeito é aquele que é igual à soma de seus divisores próprios, excluindo ele mesmo. 
Ex: 6 = 1+2+3
'''

import math

# Para encontrar todos os divisores de um número x, basta testar 
# os números inteiros de 1 até a raiz quadrada de x.

def divisores_proprios(n):
    '''Retorna os divisores próprios de n, excluindo n'''

    divisores = []
    for i in range(1, int(math.ceil(math.sqrt(n))) + 1):
        if n % i == 0:
            divisores.append(i)
            if i != n // i and n // i != n:
                divisores.append(n // i)
    return divisores


def soma_divisores(n):
    '''Retorna a soma dos divisores próprios de n'''

    return sum(divisores_proprios(n))


def numero_perfeito(n):
    '''Retorna uma string indicando se n é um número perfeito ou não'''

    return f'{n} é número perfeito pois {n} = {" + ".join(map(str, divisores_proprios(n)))}' if n == soma_divisores(n) else f'{n} não é número perfeito'


def encontrar_numeros_perfeitos(limite_inferior, limite_superior):
    '''Encontra e retorna uma lista de números perfeitos entre os limites fornecidos'''

    numeros_perfeitos = []
    print(f'Encontrando números perfeitos...')
    for i in range(limite_inferior, limite_superior + 1):
        if i == soma_divisores(i):
            numeros_perfeitos.append(i)
            print(f'{numero_perfeito(i)} = {" + ".join(map(str, divisores_proprios(i)))}')
    return numeros_perfeitos


if __name__ == "__main__":
    limite_inferior = int(input("Digite o limite inferior: "))
    limite_superior = int(input("Digite o limite superior: "))
    numeros_perfeitos = encontrar_numeros_perfeitos(limite_inferior, limite_superior)
    print(f'{", ".join(map(str, numeros_perfeitos))} são os números perfeitos entre {limite_inferior} e {limite_superior}.')