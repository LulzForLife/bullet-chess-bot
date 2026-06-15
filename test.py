from main_copy import *
import json
import tqdm

def test(fen: str, moves: list[chess.Move | None], depth: int) -> bool:
    board = EvalBoard.from_fen(fen)
    for move in moves:
        best_move = get_best_move(board, time_limit=10, max_depth=depth, print_info=False)[0]
        if move != best_move:
            return False
        board.apply(move)
    return True

def main() -> None:
    with open("testcases.json", "r") as f:
        tests: dict[str, list[list[str] | int]] = json.load(f)
    
    successes = total = 0
    for fen, m in tqdm.tqdm(tests.items()):
        moves: list[str] = m[0] # type: ignore
        depth: int = m[1] # type: ignore
        chess_moves = [chess.Move.from_uci(move) for move in moves]
        if test(fen, chess_moves, depth):
            successes += 1
        total += 1
    
    print(f"{successes} / {total} succeeded ({round((successes / total) * 100, 2)}%)")

if __name__ == "__main__":
    main()