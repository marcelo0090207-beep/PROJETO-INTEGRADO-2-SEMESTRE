SSOPY
Simulador de Sistema Operacional em Python desenvolvido para o Projeto Integrado do curso de Análise e Desenvolvimento de Sistemas da Faculdade Anhanguera.
O programa mostra, em um menu no terminal, como processos dividem o tempo da CPU, ocupam memória, esperam por entrada e saída e usam arquivos e recursos. Tudo acontece dentro de uma simulação: ele não altera os processos nem a memória real do computador.
Como executar
É necessário ter Python 3.10 ou mais recente. O projeto usa apenas a biblioteca padrão do Python.
1. Baixe o arquivo SSOPY.py.
2. Abra o terminal na pasta em que o arquivo foi salvo.
3. Execute:
   Windows:
   py SSOPY.py
   Linux:
   python3 SSOPY.py
Primeiro contato
No menu inicial, escolha 1 — Ver uma demonstração explicada. O programa cria dois processos e mostra o uso de memória, a disputa por um recurso, a espera por entrada e saída e a execução da CPU.
Depois, experimente as outras opções:
Opção	O que faz
2	Cria processos, executa ciclos de CPU e mostra as filas.
3	Mostra quais partições da memória estão livres ou ocupadas.
4	Cria, abre, escreve, lê, fecha e apaga arquivos virtuais.
5	Controla o uso simulado de impressora, disco e fita.
6	Demonstra semáforos binários e a espera por um recurso ocupado.
7	Mostra um resumo da sessão.
8	Mostra os eventos mais recentes.
9	Salva a sessão no arquivo ssopy_sessao.json.
10	Carrega a sessão salva.
11	Encerra o programa.


Ao aparecer uma sugestão entre colchetes, pressione Enter para aceitá-la. Se digitar uma opção inválida, o programa explica o problema e volta ao menu.
Conceitos representados
- Processos: cada processo tem um número (PID) e pode estar pronto, executando, bloqueado ou terminado.
- CPU: usa Round Robin com quantum de duas unidades simuladas. Um processo que ainda precisa de CPU volta para o fim da fila.
- Memória: usa First Fit para encontrar a primeira partição livre com espaço suficiente.
- Entrada e saída: um processo pode ficar bloqueado por alguns ciclos antes de voltar à fila.
- Arquivos e recursos: existem apenas dentro do simulador. Dois processos podem disputar um recurso e aguardar sua vez.
- Sessão: o estado pode ser salvo em JSON e retomado depois.
Documentação
O arquivo SSOPY_Documentacao_PDP_PDD_SDD.pdf reúne o PDP, o PDD, o SDD, uma tabela verdade da alocação de memória e o código-fonte completo ao final. Há também uma versão .docx para edição e impressão.
Autor
Marcelo Henrique Pereira Santos — Projeto Integrado, Faculdade Anhanguera, Sumaré, 2026.
