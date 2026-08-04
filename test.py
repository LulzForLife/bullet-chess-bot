from main import *
import bulletchess.utils as utils
import json
import tqdm

def test_position(fen: str, moves: list[chess.Move | None], depth: int) -> bool:
    board = EvalBoard.from_fen(fen)
    for move in moves:
        best_move = get_best_move(board, time_limit=10, max_depth=depth, print_info=False)[0]
        if move != best_move:
            return False
        board.apply(move, None, None, None)
    return True

def test_testcases(fp: str) -> None:
    with open(fp, "r") as f:
        tests: dict[str, list] = json.load(f)
    
    for fen, m in tqdm.tqdm(tests.items()):
        moves: list[str] = m[0]
        depth: int = m[1]
        chess_moves = [chess.Move.from_uci(move) for move in moves]
        if not test_position(fen, chess_moves, depth):
            raise ValueError(f"Position {fen} failed!")

def test_apply_undo(tests: int) -> None:
    for _ in tqdm.tqdm(range(tests)):
        test_position = EvalBoard()
        initial_eval = test_position.evaluate()
        while not test_position.is_game_over:
            test_position.apply(utils.random_legal_move(test_position.board), None, None, None)
        while test_position.history:
            test_position.undo()
        if test_position.evaluate() != initial_eval:
            raise ValueError("Mismatch with applying/undoing!")

def test_perft(depth: int) -> None:
    def search(b: chess.Board, depth: int) -> Generator[chess.Board]:
        if depth <= 0:
            for m in b.legal_moves():
                b.apply(m)
                yield b
                b.undo()
        else:
            for m in b.legal_moves():
                b.apply(m)
                for pos in search(b, depth - 1):
                    yield pos
                yield b
                b.undo()
    depths = {
        0: 20,
        1: 420,
        2: 9322,
        3: 206603,
        4: 5072212,
        5: 124132536,
    }
    for d in tqdm.tqdm(range(depth)):
        if not len(list(search(chess.Board(), d))) == depths[d]:
            raise ValueError(f"Error at depth {d} in perft")

def test_zobist_clash(depth: int) -> None:
    def search(b: EvalBoard, depth: int) -> Generator[EvalBoard]:
        if depth <= 0:
            for m in b.legal_moves():
                b.apply(m, None, None, None)
                yield b
                b.undo()
        else:
            for m in b.legal_moves():
                b.apply(m, None, None, None)
                yield b
                for pos in search(b, depth - 1):
                    yield pos
                b.undo()
    hash_fen = {}
    for d in tqdm.tqdm(range(depth)):
        for pos in search(EvalBoard(), d):
            pos_hash, pos_fen = pos.__hash__(), pos.fen().split()[0]
            if pos_hash in hash_fen:
                correct_fen = hash_fen[pos_hash].split()[0]
                if correct_fen != pos_fen:
                    raise ValueError(f"Hash collision between {pos_fen} and {correct_fen}")
            else:
                hash_fen[pos_hash] = pos_fen

def test_board_speed(iters: int) -> None:
    board = EvalBoard()
    move = chess.Move.from_uci("e2e4")
    s = time.perf_counter()
    board.apply(move, None, None, None)
    for _ in tqdm.tqdm(range(iters)):
        board.apply(board.undo(), None, None, None)
    board.undo()
    e = time.perf_counter()
    print(f"Average time: {(e - s) / iters}")

def main() -> None:
    test_testcases("testcases.json")
    test_apply_undo(1_000)
    test_perft(5)
    test_zobist_clash(4)
    test_board_speed(1_000_000)

if __name__ == "__main__":
    main()
