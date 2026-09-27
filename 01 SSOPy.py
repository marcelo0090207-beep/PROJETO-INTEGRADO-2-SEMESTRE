#!/usr/bin/env python3
"""SSOPY: simulador interativo de conceitos de Sistemas Operacionais.

Projeto acadêmico em Python puro. O hardware, a CPU e os arquivos são simulados.
Execute: python SSO_Projeto_Integrado_Simples_v3.py
"""
from __future__ import annotations

import json
import textwrap
from collections import deque
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path


SIZES = (64, 128, 256, 64, 256, 128, 64, 64)
RESOURCES = ("IMPRESSORA", "DISCO", "FITA")
SEMAPHORES = ("MUTEX", "RECURSO")
SAVE_FILE = "ssopy_sessao.json"


@dataclass
class Task:
    pid: int
    name: str
    priority: int
    total: int
    requested: int
    done: int = 0
    state: str = "NOVO"
    wait: str = ""
    created_at: int = 0
    finished_at: int | None = None
    open_files: list[str] = field(default_factory=list)
    resources: list[str] = field(default_factory=list)


@dataclass
class Volume:
    name: str
    owner: int
    created: str
    text: str = ""
    opened: bool = False


def table(headers: tuple[str, ...], rows: list[tuple[object, ...]], widths: tuple[int, ...]) -> str:
    def render(values: tuple[object, ...]) -> list[str]:
        cells = [textwrap.wrap(str(value), width=width, break_long_words=True) or [""]
                 for value, width in zip(values, widths)]
        height = max(map(len, cells))
        return ["  " + "  ".join(
            (cell[index] if index < len(cell) else "").ljust(width)
            for cell, width in zip(cells, widths)) for index in range(height)]
    lines = render(headers) + ["  " + "  ".join("-" * w for w in widths)]
    for values in rows:
        lines.extend(render(values))
    return "\n".join(lines)


def panel(title: str, text: str) -> str:
    return f"\n{'=' * 72}\n  {title}\n{'=' * 72}\n{text}\n{'=' * 72}"


class Laboratory:
    """Motor de eventos: CPU, memória, E/S, arquivos e exclusão mútua."""

    def __init__(self):
        self.tasks: dict[int, Task] = {}
        self.ready: deque[int] = deque()
        self.io: dict[int, int] = {}
        self.partitions: list[int | None] = [None] * len(SIZES)
        self.files: dict[str, Volume] = {}
        self.resources: dict[str, int | None] = dict.fromkeys(RESOURCES)
        self.resource_queues: dict[str, deque[int]] = {r: deque() for r in RESOURCES}
        self.semaphores: dict[str, int | None] = dict.fromkeys(SEMAPHORES)
        self.semaphore_queues: dict[str, deque[int]] = {r: deque() for r in SEMAPHORES}
        self.events: list[dict] = []
        self.next_pid = 1000
        self.clock = 0
        self.cpu_used = 0
        self.quantum = 2
        self.io_total = 0
        self.switches = 0

    def emit(self, tag: str, detail: str) -> str:
        self.events.append({"time": self.clock, "tag": tag, "detail": detail})
        return detail

    def living(self, pid: int) -> Task:
        task = self.tasks.get(pid)
        if task is None or task.state == "TERMINADO":
            raise ValueError("PID inexistente ou já terminado. Consulte PS.")
        return task

    def create(self, name: str, priority: int, total: int, size: int) -> str:
        if not name.strip() or len(name) > 20 or not 1 <= priority <= 10 or total < 1 or size < 1:
            raise ValueError("Use nome (até 20 caracteres), prioridade 1–10, CPU > 0 e RAM > 0.")
        slot = next((i for i, capacity in enumerate(SIZES)
                     if self.partitions[i] is None and capacity >= size), None)
        if slot is None:
            raise ValueError("First Fit: nenhuma partição livre comporta o pedido; consulte MEM.")
        pid = self.next_pid
        self.next_pid += 1
        task = Task(pid, name, priority, total, size, state="PRONTO", created_at=self.clock)
        self.tasks[pid] = task
        self.partitions[slot] = pid
        self.ready.append(pid)
        return self.emit("PROCESSO", f"PID {pid} criado em P{slot + 1} ({SIZES[slot]} KB); pedido {size} KB.")

    def wake(self, pid: int) -> None:
        task = self.tasks[pid]
        task.state, task.wait = "PRONTO", ""
        if pid not in self.ready:
            self.ready.append(pid)

    def block(self, task: Task, reason: str) -> None:
        task.state, task.wait = "BLOQUEADO", reason
        self.ready = deque(x for x in self.ready if x != task.pid)

    def tick(self) -> str:
        # A espera de E/S diminui uma vez por despacho, inclusive quando a CPU está ociosa.
        for pid in list(self.io):
            self.io[pid] -= 1
            if self.io[pid] == 0:
                del self.io[pid]
                self.wake(pid)
                self.emit("E/S", f"PID {pid} concluiu E/S e voltou à fila PRONTO.")
        if not self.ready:
            self.clock += 1
            return self.emit("CPU", "CPU ociosa por uma unidade de tempo.")
        pid = self.ready.popleft()
        task = self.living(pid)
        task.state = "EXECUTANDO"
        amount = min(self.quantum, task.total - task.done)
        task.done += amount
        self.cpu_used += amount
        self.clock += amount
        self.switches += 1
        result = f"PID {pid} ({task.name}): {task.done}/{task.total} CPU"
        self.emit("CPU", f"Round Robin despachou PID {pid} por {amount} unidade(s).")
        if task.done == task.total:
            self.finish(pid)
            return result + " -> TERMINADO; memória e recursos liberados."
        task.state = "PRONTO"
        self.ready.append(pid)
        return result + " -> PRONTO; voltou ao fim da fila."

    def request_io(self, pid: int, duration: int) -> str:
        task = self.living(pid)
        if task.state != "PRONTO" or not 1 <= duration <= 20:
            raise ValueError("A E/S exige processo PRONTO e duração entre 1 e 20 ciclos.")
        self.block(task, "E/S")
        self.io[pid] = duration
        self.io_total += 1
        return self.emit("E/S", f"PID {pid} bloqueado por {duration} ciclo(s) de E/S.")

    def finish(self, pid: int) -> str:
        task = self.living(pid)
        self.ready = deque(x for x in self.ready if x != pid)
        self.io.pop(pid, None)
        for index, occupant in enumerate(self.partitions):
            if occupant == pid:
                self.partitions[index] = None
        for volume in self.files.values():
            if volume.owner == pid:
                volume.opened = False
        task.open_files.clear()
        for name in list(task.resources):
            self._release(self.resources, self.resource_queues, name, pid)
        for name, owner in list(self.semaphores.items()):
            if owner == pid:
                self._release(self.semaphores, self.semaphore_queues, name, pid)
        for waiting in (*self.resource_queues.values(), *self.semaphore_queues.values()):
            try:
                waiting.remove(pid)
            except ValueError:
                pass
        task.state, task.wait, task.finished_at = "TERMINADO", "", self.clock
        return self.emit("PROCESSO", f"PID {pid} terminado; partição e posses liberadas.")

    def _release(self, owners: dict, queues: dict, name: str, pid: int) -> None:
        owners[name] = None
        self.tasks[pid].resources = [x for x in self.tasks[pid].resources if x != name]
        while queues[name]:
            candidate = queues[name].popleft()
            if self.tasks[candidate].state != "TERMINADO":
                owners[name] = candidate
                if owners is self.resources:
                    self.tasks[candidate].resources.append(name)
                self.wake(candidate)
                self.emit("FILA", f"{name} transferido ao PID {candidate} (primeiro da fila).")
                break

    def acquire(self, kind: str, name: str, pid: int) -> str:
        task = self.living(pid)
        owners = self.resources if kind == "RECURSO" else self.semaphores
        queues = self.resource_queues if kind == "RECURSO" else self.semaphore_queues
        if name not in owners:
            raise ValueError(f"{kind} desconhecido. Consulte {kind}S.")
        if owners[name] == pid:
            raise ValueError(f"PID {pid} já possui {name}.")
        if task.state != "PRONTO":
            raise ValueError("A solicitação exige processo PRONTO.")
        if owners[name] is not None:
            self.block(task, f"{kind} {name}")
            queues[name].append(pid)
            return self.emit("FILA", f"{name} ocupado; PID {pid} entrou na fila e ficou BLOQUEADO.")
        owners[name] = pid
        if kind == "RECURSO":
            task.resources.append(name)
        return self.emit(kind, f"PID {pid} adquiriu {name}.")

    def release(self, kind: str, name: str, pid: int) -> str:
        self.living(pid)
        owners = self.resources if kind == "RECURSO" else self.semaphores
        queues = self.resource_queues if kind == "RECURSO" else self.semaphore_queues
        if name not in owners or owners[name] != pid:
            raise ValueError("Só o PID proprietário pode liberar esse item.")
        self._release(owners, queues, name, pid)
        return self.emit(kind, f"PID {pid} liberou {name}; próximo da fila, se houver, recebeu a posse.")

    def file(self, operation: str, name: str, pid: int, text: str = "") -> str:
        task = self.living(pid)
        key = name.upper()
        if not key or len(key) > 32 or "/" in key or "\\" in key:
            raise ValueError("Nome de arquivo inválido (até 32 caracteres, sem barras).")
        if operation == "CRIAR":
            if key in self.files:
                raise ValueError("Arquivo já existe.")
            self.files[key] = Volume(key, pid, datetime.now().strftime("%d/%m/%Y %H:%M"))
            return self.emit("ARQUIVO", f"{key} criado para PID {pid}.")
        volume = self.files.get(key)
        if volume is None or volume.owner != pid:
            raise ValueError("Arquivo inexistente ou não pertence ao PID informado.")
        if operation == "ABRIR":
            if volume.opened:
                raise ValueError("Arquivo já aberto.")
            volume.opened = True
            task.open_files.append(key)
        elif operation == "FECHAR":
            if not volume.opened:
                raise ValueError("Arquivo já fechado.")
            volume.opened = False
            task.open_files.remove(key)
        elif operation == "LER":
            if not volume.opened:
                raise ValueError("Abra o arquivo antes de ler.")
            self.emit("ARQUIVO", f"PID {pid} leu {key}.")
            return volume.text or "(arquivo vazio)"
        elif operation == "ESCREVER":
            if not volume.opened or not text:
                raise ValueError("Abra o arquivo e informe texto para escrever.")
            volume.text += text + "\n"
        elif operation == "APAGAR":
            if volume.opened:
                raise ValueError("Feche o arquivo antes de apagar.")
            del self.files[key]
        else:
            raise ValueError("Operação de arquivo desconhecida.")
        return self.emit("ARQUIVO", f"PID {pid}: {operation} {key}.")

    def memory_view(self) -> str:
        rows = []
        for index, size in enumerate(SIZES):
            pid = self.partitions[index]
            requested = self.tasks[pid].requested if pid is not None else 0
            used = round(16 * requested / size) if pid is not None else 0
            bar = "#" * used + "." * (16 - used)
            rows.append((f"P{index + 1}", f"{size} KB", pid or "livre", f"{requested} KB", bar))
        occupied = sum(SIZES[i] for i, pid in enumerate(self.partitions) if pid is not None)
        requested_total = sum(self.tasks[pid].requested for pid in self.partitions if pid is not None)
        return panel("MAPA DA MEMÓRIA  |  FIRST FIT", table(
            ("PART.", "CAPACIDADE", "PID", "PEDIDO", "USO DA PARTIÇÃO"), rows,
            (6, 11, 8, 8, 18)) +
            f"\n\n  Total: 1024 KB   Reservado: {occupied} KB   Livre: {1024 - occupied} KB"
            f"\n  Pedido real: {requested_total} KB   Fragmentação interna: {occupied - requested_total} KB")

    def timeline(self, limit: int = 15) -> str:
        rows = [(f"t={e['time']}", e["tag"], e["detail"]) for e in self.events[-limit:]]
        return panel("LINHA DO TEMPO", table(("TEMPO", "TIPO", "EVENTO"), rows,
                                         (7, 10, 48)) if rows else "  Nenhum evento registrado.")

    def snapshot(self) -> dict:
        return {"version": 2, "tasks": [asdict(t) for t in self.tasks.values()],
                "ready": list(self.ready), "io": self.io, "partitions": self.partitions,
                "files": [asdict(f) for f in self.files.values()],
                "resources": self.resources,
                "resource_queues": {k: list(v) for k, v in self.resource_queues.items()},
                "semaphores": self.semaphores,
                "semaphore_queues": {k: list(v) for k, v in self.semaphore_queues.items()},
                "events": self.events, "next_pid": self.next_pid, "clock": self.clock,
                "cpu_used": self.cpu_used, "quantum": self.quantum,
                "io_total": self.io_total, "switches": self.switches}

    def save(self, path: Path) -> str:
        path.write_text(json.dumps(self.snapshot(), indent=2, ensure_ascii=False), encoding="utf-8")
        return f"Sessão salva em {path.name}. Inclui processos, arquivos e eventos."

    @classmethod
    def load(cls, path: Path) -> Laboratory:
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("version") != 2:
            raise ValueError("Formato de sessão incompatível.")
        obj = cls()
        obj.tasks = {x["pid"]: Task(**x) for x in data["tasks"]}
        obj.ready = deque(data["ready"])
        obj.io = {int(k): v for k, v in data["io"].items()}
        obj.partitions = data["partitions"]
        obj.files = {x["name"]: Volume(**x) for x in data["files"]}
        obj.resources = data["resources"]
        obj.resource_queues = {k: deque(v) for k, v in data["resource_queues"].items()}
        obj.semaphores = data["semaphores"]
        obj.semaphore_queues = {k: deque(v) for k, v in data["semaphore_queues"].items()}
        obj.events = data["events"]
        for attr in ("next_pid", "clock", "cpu_used", "quantum", "io_total", "switches"):
            setattr(obj, attr, data[attr])
        obj.validate()
        return obj

    def validate(self) -> None:
        if len(self.partitions) != len(SIZES) or self.quantum < 1 or self.clock < 0:
            raise ValueError("Sessão inconsistente.")
        active = {pid for pid, task in self.tasks.items() if task.state != "TERMINADO"}
        if (len(active) != sum(pid is not None for pid in self.partitions) or
                set(self.ready) != {pid for pid in active if self.tasks[pid].state == "PRONTO"} or
                len(self.ready) != len(set(self.ready)) or
                any(pid not in active for pid in self.partitions if pid is not None)):
            raise ValueError("Sessão inconsistente: processos e memória não correspondem.")
        for pid, task in self.tasks.items():
            if task.state == "BLOQUEADO" and pid not in self.io and not any(
                pid in q for q in (*self.resource_queues.values(), *self.semaphore_queues.values())
            ):
                raise ValueError("Sessão inconsistente: bloqueio sem espera.")
        for mapping in (self.resources, self.semaphores):
            if any(pid is not None and pid not in active for pid in mapping.values()):
                raise ValueError("Sessão inconsistente: proprietário encerrado.")


class SimpleConsole:
    """Passo a passo por números, com os conceitos visíveis nas respostas."""

    def __init__(self):
        self.so = Laboratory()
        self.save_path = Path(__file__).resolve().parent / SAVE_FILE

    @staticmethod
    def choose(title: str, options: tuple[str, ...]) -> str:
        print(panel(title, "\n".join(f"  {i}. {option}" for i, option in enumerate(options, 1))))
        return input("Escolha um número: ").strip()

    @staticmethod
    def ask(label: str, default: str | None = None) -> str:
        suffix = f" [{default}]" if default is not None else ""
        answer = input(f"{label}{suffix}: ").strip()
        return answer or (default or "")

    @classmethod
    def number(cls, label: str, default: int | None = None) -> int:
        answer = cls.ask(label, str(default) if default is not None else None)
        try:
            return int(answer)
        except ValueError as exc:
            raise ValueError(f"{label}: digite um número inteiro.") from exc

    def pid(self) -> int:
        active = [t for t in self.so.tasks.values() if t.state != "TERMINADO"]
        if not active:
            raise ValueError("Ainda não há processos ativos. Escolha Criar processo primeiro.")
        print("Processos disponíveis:")
        for task in active:
            print(f"  {task.pid} = {task.name} ({task.state})")
        return self.number("Número do processo (PID)", active[-1].pid)

    def process_list(self) -> str:
        rows = [(t.pid, t.name, t.state, f"{t.done}/{t.total}", t.requested, t.wait or "-")
                for t in self.so.tasks.values()]
        return panel("PROCESSOS  |  CPU usada / CPU necessária", table(
            ("PID", "NOME", "ESTADO", "CPU", "RAM KB", "ESPERA"), rows,
            (6, 17, 11, 7, 7, 16)) if rows else "  Nenhum processo criado.")

    def queues(self) -> str:
        lines = [f"  Esperando a CPU: {list(self.so.ready) or 'ninguém'}",
                 f"  Fazendo entrada/saída: {self.so.io or 'ninguém'}"]
        for name, queue in (*self.so.resource_queues.items(), *self.so.semaphore_queues.items()):
            lines.append(f"  Esperando {name}: {list(queue) or 'ninguém'}")
        return panel("FILAS  |  QUEM ESTÁ ESPERANDO?", "\n".join(lines))

    def processes(self) -> None:
        while True:
            option = self.choose("PROCESSOS  |  CADA PROGRAMA ESPERA SUA VEZ", (
                "Ver os processos", "Criar processo", "Dar uma vez de CPU",
                "Dar várias vezes de CPU", "Colocar em espera de E/S",
                "Encerrar processo", "Ver as filas", "Voltar"))
            if option == "8":
                return
            if option == "1":
                print(self.process_list())
            elif option == "2":
                name = self.ask("Nome do programa", "Editor")
                priority = self.number("Prioridade de 1 a 10 (registrada)", 2)
                total = self.number("Quantas unidades de CPU ele precisa", 5)
                size = self.number("Quanta memória ele pede, em KB", 64)
                print(self.so.create(name, priority, total, size))
                print("Pronto! Agora veja a opção 1, depois use a opção 3.")
            elif option in ("3", "4"):
                count = self.number("Quantas vezes", 3) if option == "4" else 1
                if not 1 <= count <= 100:
                    raise ValueError("Escolha de 1 a 100 vezes.")
                for _ in range(count):
                    print("  " + self.so.tick())
                print("Dica: veja a lista para conferir quem terminou ou voltou à fila.")
            elif option == "5":
                pid = self.pid()
                cycles = self.number("Quantas vezes ele espera", 2)
                print(self.so.request_io(pid, cycles))
            elif option == "6":
                print(self.so.finish(self.pid()))
            elif option == "7":
                print(self.queues())
            else:
                print("Escolha um número de 1 a 8.")

    def show_files(self) -> str:
        rows = [(f.name, f.owner, len(f.text.encode("utf-8")),
                 "ABERTO" if f.opened else "FECHADO") for f in self.so.files.values()]
        return panel("ARQUIVOS DE FAZ DE CONTA", table(
            ("NOME", "DONO", "BYTES", "ESTADO"), rows,
            (25, 8, 8, 9)) if rows else "  Ainda não há arquivos.")

    def files(self) -> None:
        actions = ("Ver arquivos", "Criar", "Abrir", "Escrever", "Ler", "Fechar", "Apagar", "Voltar")
        operations = {"2": "CRIAR", "3": "ABRIR", "4": "ESCREVER", "5": "LER",
                      "6": "FECHAR", "7": "APAGAR"}
        while True:
            option = self.choose("ARQUIVOS  |  UM CADERNO PARA CADA PROCESSO", actions)
            if option == "8":
                return
            if option == "1":
                print(self.show_files())
            elif option in operations:
                print("Ordem sugerida: criar → abrir → escrever → ler → fechar → apagar.")
                name = self.ask("Nome do arquivo", "notas.txt")
                pid = self.pid()
                content = self.ask("O que escrever") if option == "4" else ""
                print(self.so.file(operations[option], name, pid, content))
            else:
                print("Escolha um número de 1 a 8.")

    def sharing(self, semaphore: bool = False) -> None:
        title = "SEMÁFOROS  |  UMA CHAVE POR VEZ" if semaphore else "RECURSOS  |  UM DONO POR VEZ"
        names = SEMAPHORES if semaphore else RESOURCES
        while True:
            option = self.choose(title, ("Ver quem está usando", "Pedir", "Liberar", "Ver filas", "Voltar"))
            if option == "5":
                return
            if option == "1":
                owners = self.so.semaphores if semaphore else self.so.resources
                queues = self.so.semaphore_queues if semaphore else self.so.resource_queues
                rows = [(name, owner or "livre", list(queues[name]) or "ninguém")
                        for name, owner in owners.items()]
                print(panel(title, table(("NOME", "DONO", "ESPERANDO"), rows, (17, 10, 25))))
            elif option in ("2", "3"):
                print("Opções: " + ", ".join(names))
                name = self.ask("Qual deles", names[0]).upper()
                pid = self.pid()
                kind = "SEMAFORO" if semaphore else "RECURSO"
                print(self.so.acquire(kind, name, pid) if option == "2"
                      else self.so.release(kind, name, pid))
                print("Se já tinha dono, observe o processo BLOQUEADO na opção Ver filas.")
            elif option == "4":
                print(self.queues())
            else:
                print("Escolha um número de 1 a 5.")

    def status(self) -> str:
        active = sum(t.state != "TERMINADO" for t in self.so.tasks.values())
        occupied = sum(SIZES[i] for i, x in enumerate(self.so.partitions) if x is not None)
        return panel("RESUMO DA AULA", f"""  Tempo simulado                 {self.so.clock}
  Trabalho feito pela CPU        {self.so.cpu_used}
  Vezes que a CPU trabalhou      {self.so.switches}
  Processos criados              {len(self.so.tasks)}
  Processos ativos               {active}
  Processos terminados           {len(self.so.tasks) - active}
  Memória reservada              {occupied} de 1024 KB
  Esperas de E/S criadas         {self.so.io_total}
  Arquivos virtuais              {len(self.so.files)}
  Acontecimentos registrados     {len(self.so.events)}""")

    def demo(self) -> None:
        if any(t.state != "TERMINADO" for t in self.so.tasks.values()):
            raise ValueError("A demonstração precisa de memória livre. Encerre os processos atuais primeiro.")
        print("PASSO 1: criar Editor e Browser.")
        a = self.so.next_pid
        print(self.so.create("Editor", 2, 6, 64))
        b = self.so.next_pid
        print(self.so.create("Browser", 3, 4, 128))
        print("PASSO 2: veja onde cada um ficou na memória.")
        print(self.so.memory_view())
        print("PASSO 3: disputar o DISCO. Um deles precisa esperar.")
        print(self.so.acquire("RECURSO", "DISCO", a))
        print(self.so.acquire("RECURSO", "DISCO", b))
        print(self.queues())
        print("PASSO 4: liberar o DISCO; quem esperava recebe a vez.")
        print(self.so.release("RECURSO", "DISCO", a))
        print("PASSO 5: Editor espera E/S e a CPU atende quem está pronto.")
        print(self.so.request_io(a, 2))
        while any(self.so.tasks[pid].state != "TERMINADO" for pid in (a, b)):
            print("  " + self.so.tick())
        print("FIM: os dois terminaram; memória e DISCO foram liberados.")
        print("Agora escolha Ver o resumo e depois Ver a história.")

    def run(self) -> None:
        print("\nBem-vindo ao SSOPY! Você só precisa escolher números.")
        print("Pense numa fila: a CPU dá a vez a um processo por vez.")
        while True:
            try:
                active = sum(t.state != "TERMINADO" for t in self.so.tasks.values())
                choice = self.choose(
                    f"SSOPY  |  tempo {self.so.clock}  |  {active} processo(s) ativo(s)", (
                        "Ver uma demonstração explicada", "Usar processos e CPU",
                        "Ver as caixinhas da memória", "Usar arquivos",
                        "Dividir recursos", "Usar semáforos", "Ver o resumo",
                        "Ver a história do que aconteceu", "Guardar a sessão",
                        "Continuar uma sessão salva", "Sair"))
                if choice == "1":
                    self.demo()
                elif choice == "2":
                    self.processes()
                elif choice == "3":
                    print(self.so.memory_view())
                elif choice == "4":
                    self.files()
                elif choice == "5":
                    self.sharing()
                elif choice == "6":
                    self.sharing(semaphore=True)
                elif choice == "7":
                    print(self.status())
                elif choice == "8":
                    print(self.so.timeline(20))
                elif choice == "9":
                    print(self.so.save(self.save_path))
                elif choice == "10":
                    if not self.save_path.is_file():
                        raise ValueError("Não existe sessão salva. Escolha 9 primeiro.")
                    self.so = Laboratory.load(self.save_path)
                    print("Sua sessão voltou! Veja processos ou memória.")
                elif choice == "11":
                    print("Até logo! Se não guardou a sessão, os dados temporários acabam aqui.")
                    return
                else:
                    print("Digite um número de 1 a 11.")
            except (EOFError, KeyboardInterrupt):
                print("\nAté logo!")
                return
            except (ValueError, OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
                print(f"Não deu certo: {exc}")
                print("Você pode tentar de novo pelo menu.")


if __name__ == "__main__":
    SimpleConsole().run()
