import json
import os
import sys
import time
import zipfile
from pathlib import Path
from typing import List, Hashable
from dotenv import load_dotenv
load_dotenv()

from jz3.src.run_solvers import run_solvers
# import sudoku_experiment_demo.Sudoku as Sudoku
import Sudoku
from sql_warp import Sql_db_wrapper

def get_seed_from_env():
    return os.getenv("FIX_SEED")

FULL_CONDITIONS = [(classic, distinct, percol, nonum, prefill)  # must be hashable
                   for classic in (True, False)
                   for distinct in (True, False)
                   for percol in (True, False)
                   for nonum in (True, False) if not (distinct and nonum) # distinct and nonum cannot be both true
                   for prefill in (True, False)]
assert isinstance(FULL_CONDITIONS[0], Hashable), "Conditions MUST be HASHABLE"


def to_str(bool_list) -> str:
    if len(bool_list) == 6:
        return ''.join(("classic-" if bool_list[0] else "argyle-",
                        "distinct-" if bool_list[1] else "PbEq-",
                        "percol-" if bool_list[2] else "inorder-",
                        "is_bool-" if bool_list[3] else "is_num-",
                        "prefill-" if bool_list[4] else "no_prefill-",
                        "gen_time" if bool_list[5] else "solve_time"))
    if len(bool_list) == 5:
        return ''.join(("classic-" if bool_list[0] else "argyle-",
                        "distinct-" if bool_list[1] else "PbEq-",
                        "percol-" if bool_list[2] else "inorder-",
                        "is_bool-" if bool_list[3] else "is_num-",
                        "prefill-" if bool_list[4] else "no_prefill-"))


def to_bool(condition_str: str) -> list[bool]:
    condition_lst = condition_str.split('-')
    assert len(condition_lst) >= 4, "Cannot convert condition string"
    if len(condition_lst) == 4:
        return [True if condition_lst[0].lower() == "classic" else False,
                True if condition_lst[1].lower() == "distinct" else False,
                True if condition_lst[2].lower() == "percol" else False,
                True if condition_lst[3].lower() == "is_bool" else False,
                True if condition_lst[4].lower() == "prefill" else False,
                True if condition_lst[5].lower() == "gen_time" else False]
    pass

def generate_smt2_filename(problem_type, constraint):
    return f"{problem_type}-{constraint}-{time.time()}.smt2"

def save_smt2_file(smt2_str, filename, directory="problems_instances/whole_problem_records/smt2_files"):
    if not os.path.exists(directory):
        os.makedirs(directory)
    file_path = os.path.join(directory, filename)
    with open(file_path, 'w') as file:
        file.write(smt2_str)
    return file_path

def update_mapping(mapping_file_path, grid, constraint, smt2_file_path):
    mapping_dict = {
        "problem": {
            "grid": grid,
        },
        constraint: {
            "smt_path": smt2_file_path,
        }
    }


def run_experiment_once(single_condition: bool, *args,
                        start_condition: List[bool] = [],
                        start_from_next: bool = False,
                        curr_line_path: str = './sudoku_database/curr_line_of_solving_full_sudokus.txt',
                        classic_full_path: str = './sudoku_database/classic_full_sudokus.txt',
                        argyle_full_path: str = './sudoku_database/argyle_full_sudokus.txt',
                        classic_holes_path: str = './sudoku_database/classic_holes_sudokus.txt',
                        argyle_holes_path: str = './sudoku_database/argyle_holes_sudokus.txt',
                        hard_sudoku_dir: str = "./problems_instances/particular_hard_instances_records/txt_files/",
                        time_record_dir: str = './time-record/whole_problem_time_records',
                        hard_smt_log_dir: str = '',
                        verbose: bool = False):
    """
    Generate full sudokus and holes sudokus under different constraints and store the time to a specific location.

    Args:
        single_condition (bool): If True, only the start_condition is used. If False, all conditions are used.
        *args: Additional arguments passed to the function.
        start_condition (List[bool]): The starting condition. If empty, all conditions are used.
        start_from_next (bool): If True, starts from the next condition after start_condition.
        curr_line_path (str): Path to the file storing the current line of solving full sudokus.
        classic_full_path (str): Path to the file storing classic full sudokus.
        argyle_full_path (str): Path to the file storing argyle full sudokus.
        classic_holes_path (str): Path to the file storing classic holes sudokus.
        argyle_holes_path (str): Path to the file storing argyle holes sudokus.
        hard_sudoku_dir (str): Directory path for storing hard sudoku instances.
        time_record_dir (str): Directory path for storing time records.
        hard_smt_log_dir (str): Path for storing hard SMT logs.
        verbose (bool): If True, prints verbose output.

    Returns:
        None
    """
    total_time_start = time.time()
    try:
        with open(curr_line_path, 'r') as f:
            curr_line = eval(f.readline()) # Keep track of which full sudoku to continue_reading with
    except Exception as e:
        print(e)

    if single_condition:
        conditions = [start_condition]
    else:
        conditions = FULL_CONDITIONS
        if start_condition:
            conditions = conditions[conditions.index(tuple(start_condition)) + start_from_next:]

    seed = get_seed_from_env() or time.time()
    print(f'Generating full sudokus: \n'
          f'{"-" * len(conditions)}Total Conditions: {len(conditions)}')
    for condition in conditions:
        if condition[0]:
            full_sudoku_path = classic_full_path
            hard_sudoku_path = os.path.join(hard_sudoku_dir, 'hard_classic_instances.txt')
        else:
            full_sudoku_path = argyle_full_path
            hard_sudoku_path = os.path.join(hard_sudoku_dir, 'hard_argyle_instance.txt')

        condition_name = to_str(condition) + 'full_time'
        print('-', end="")

        full_time, full_penalty, _ = Sudoku.gen_full_sudoku(*condition, hard_smt_logPath=hard_smt_log_dir,
                                                         hard_sudoku_logPath=hard_sudoku_path,
                                                         store_sudoku_path=full_sudoku_path, seed=seed)
        # sql db time log
        db_dir = os.path.join(time_record_dir, condition_name + '.db')
        table_name = "example"  # TODO: change this into a parameter

        wrapper = Sql_db_wrapper(path=db_dir, table_name=table_name, columns={"ID": "INTEGER PRIMARY KEY",
                                                                              "time_taken": "FLOAT",
                                                                              "timeout_count": "INTEGER"})
        # column 0 is the Primary Key.
        wrapper[1:].append([full_time, full_penalty])
        del wrapper

        # txt file timelog
        os.makedirs(time_record_dir, exist_ok=True)
        with open(os.path.join(time_record_dir, condition_name + '.txt'), 'a') as f:
            f.write(f'{full_time},{full_penalty}\n')

    print("\nGenerating holes sudokus: \n"
          f'{"-" * len(conditions)}Total Conditions: {len(conditions)}')

    with open(classic_full_path, 'r') as f:
        if classic_full_path in curr_line:
            f.seek(curr_line[classic_full_path])
        classic_sudoku_lst = f.readline()[:-1]  # get rid of new line character
        curr_line[classic_full_path] = f.tell()
    classic_hard_sudoku_path = os.path.join(hard_sudoku_dir, 'hard_classic_instances.txt')

    with open(argyle_full_path, 'r') as f:
        if argyle_full_path in curr_line:
            f.seek(curr_line[argyle_full_path])
        argyle_sudoku_lst = f.readline()[:-1]  # get rid of new line character
        curr_line[argyle_full_path] = f.tell()
    argyle_hard_sudoku_path = os.path.join(hard_sudoku_dir, 'hard_argyle_instance.txt')

    for condition in conditions:
        if condition[0]:
            sudoku_lst = classic_sudoku_lst
            holes_sudoku_path = classic_holes_path
            hard_sudoku_path = classic_hard_sudoku_path
        else:
            sudoku_lst = argyle_sudoku_lst
            holes_sudoku_path = argyle_holes_path
            hard_sudoku_path = argyle_hard_sudoku_path

        condition_name = to_str(condition) + 'holes_time'
        if verbose:
            print(f'Processing holes sudoku {condition_name}')
        print('-', end="")
        holes_time, holes_penalty = Sudoku.gen_holes_sudoku(eval(sudoku_lst), *condition,
                                                            hard_smt_log_dir=hard_smt_log_dir,
                                                            hard_sudoku_logPath=hard_sudoku_path,
                                                            store_sudoku_path=holes_sudoku_path, seed=seed)
        if verbose:
            print(f'\tTime taken: {holes_time}')

        # sql db time log
        db_dir = os.path.join(time_record_dir, condition_name + '.db')
        table_name = "example"  # TODO: change this into a parameter

        wrapper = Sql_db_wrapper(path=db_dir, table_name=table_name, columns={"ID": "INTEGER PRIMARY KEY",
                                                                              "time_taken": "FLOAT",
                                                                              "timeout_count": "INTEGER"})
        # column 0 is the Primary Key.
        wrapper[1:].append([holes_time, holes_penalty])
        del wrapper

        # txt file timelog
        with open(os.path.join(time_record_dir, condition_name + '.txt'), 'a+') as f_holes:
            f_holes.write(f'{holes_time},{holes_penalty}\n')


    par_dir = Path(curr_line_path).parent
    os.makedirs(par_dir, exist_ok=True)
    with open(curr_line_path, 'w') as f:
        f.truncate()
        f.write(str(curr_line))
    print("Ran experiment once")
    total_time_end = time.time()
    print(f"Total time taken: {total_time_end-total_time_start}")





def load_and_alternative_solve_hard_once(hard_instances_txt_log_dir: str, is_classic: bool, num_iter: int,
                                    currline_path="curr_instance_line.txt", timeout=5,
                                    hard_smt_dir="./problems_instances/particular_hard_instances_records/smt2_files/",
                                    time_record_dir:str=""):
    """
    Writes a dictionary with {problem: , cond_1_time: , cond_2_time: cond_3_time: cond_4_time: ...}
    Condition[0] MUST be TRUE when classic and FALSE when argyle
    :param file_path:
    :return: None
    """
    if not os.path.exists(hard_instances_txt_log_dir):
        print(f"Provided directory does not exist, creating new directory: {hard_instances_txt_log_dir}")
        os.makedirs(hard_instances_txt_log_dir)

    if is_classic:
        hard_instances_file_path = os.path.join(hard_instances_txt_log_dir, "hard_classic_instances.txt")
        store_comparison_file_path = os.path.join(time_record_dir,"classic_time.txt")
    else:
        hard_instances_file_path = os.path.join(hard_instances_txt_log_dir, "hard_argyle_instance.txt")
        store_comparison_file_path = os.path.join(time_record_dir,"argyle_time.txt")

    with open(hard_instances_file_path, 'r+') as fr:
        # set up currline file when running the script for the first time:
        if not os.path.exists(currline_path):
            with open(currline_path,'w') as ftempw:
                ftempw.write(str({"classic": 0, "argyle": 0, "seed": 40}))

        with open(currline_path, "r") as ftempr:
            argyle_and_classic_curr_line = ftempr.readline()
            if argyle_and_classic_curr_line == '':
                argyle_and_classic_curr_line = {"classic": 0, "argyle": 0, "seed": 40}
            else:
                argyle_and_classic_curr_line = eval(argyle_and_classic_curr_line)
        curr_line_num: int = argyle_and_classic_curr_line.get("classic" if is_classic else "argyle", 0)
        argyle_and_classic_curr_line[
            "classic" if is_classic else "argyle"] = curr_line_num + num_iter  # record read lines up till now

        # skip current line numbers
        for _ in range(curr_line_num):
            fr.readline()

        for index in range(num_iter):
            line_to_solve = fr.readline()
            if line_to_solve == '\n':
                print("Encountered an empty new line, skipping the empty line")
                continue
            elif line_to_solve=='':
                print("Not enough hard instances for to solve for\nExiting the program, consider running more experiments to find more hard instances. ")
                sys.exit()
            line_to_solve = line_to_solve.strip()

            try:
                log_entry = json.loads(line_to_solve)
            except json.JSONDecodeError as e:
                print(f"Error parsing JSON line {line_to_solve}: {e.msg}\nContinuing")
                continue

            store_result_dict = {}
            # store problem and smt path
            store_result_dict["problem"] = {
                "grid": log_entry['grid'],
                "index": log_entry['index'],
                "try_Val": log_entry['try_Val'],
                "assert_equals": log_entry['assert_equals'],
                "is_sat": log_entry['is_sat']
            }
            seed = time.time()
            # solve with other conditions
            CorAconditions = [ele for ele in FULL_CONDITIONS if ele[0] == log_entry['condition_bool'][0]]
            for CorAcondition in CorAconditions:
                if CorAcondition not in store_result_dict:
                    store_result_dict[CorAcondition] = {}  # initialize the dictionary
                if "smt_path" not in store_result_dict[CorAcondition]:
                    single_condition_smt_path = Sudoku.generate_smt_for_particular_instance(store_result_dict["problem"]["grid"],
                                                                                            CorAcondition,
                                                                                            store_result_dict["problem"]["index"],
                                                                                            store_result_dict["problem"]["try_Val"],
                                                                                            store_result_dict["problem"]["is_sat"],
                                                                                            store_result_dict["problem"]["assert_equals"],
                                                                                            smt_dir=hard_smt_dir,seed=seed)
                    store_result_dict[CorAcondition]["smt_path"] = single_condition_smt_path
                else:
                    single_condition_smt_path = store_result_dict["smt_path"]

                store_result_dict[CorAcondition] = run_solvers(smt2_file=single_condition_smt_path, time_out=timeout)


            # sql db time record file
            if is_classic:
                db_dir = os.path.join(time_record_dir,"classic_time.db")
            else:
                db_dir = os.path.join(time_record_dir,"argyle_time.db")
            table_name = "example"  # TODO: change this into a parameter

            wrapper = Sql_db_wrapper(path=db_dir, table_name=table_name, columns={"ID": "INTEGER PRIMARY KEY",
                                                                                  #
                                                                                  "problem_instance": "INTEGER",
                                                                                  "problem_grid": "TEXT",
                                                                                  "problem_index": "TEXT",
                                                                                  "problem_tryval": "INTEGER",
                                                                                  "problem_assert_equals": "BOOL",
                                                                                  "problem_is_sat": "TEXT",
                                                                                  #
                                                                                  "cond_is_classic": "BOOL",
                                                                                  "cond_is_distinct": "BOOL",
                                                                                  "cond_is_per_col": "BOOL",
                                                                                  "cond_is_no_num": "BOOL",
                                                                                  "cond_is_profill": "BOOL",
                                                                                  #
                                                                                  "res_time_z3": "FLOAT",
                                                                                  "res_timeout_z3": "BOOL"})

            for key in store_result_dict.keys():
                if isinstance(key, str):
                    continue
                # column 0 is the Primary Key.
                wrapper[1:].append([
                    index,
                    store_result_dict["problem"]["grid"],
                    str(store_result_dict["problem"]["index"])[1:-1],
                    store_result_dict["problem"]['try_Val'],
                    store_result_dict["problem"]["assert_equals"],
                    store_result_dict["problem"]["is_sat"],
                    key[0],
                    key[1],
                    key[2],
                    key[3],
                    key[4],
                    store_result_dict[key]['z3'][0],
                    store_result_dict[key]['z3'][1],
                ])
            del wrapper

            # write time dictionary to the time record file
            os.makedirs(time_record_dir, exist_ok=True)
            with open(store_comparison_file_path, 'a+') as fw:
                fw.write(str(store_result_dict) + '\n')
        with open(currline_path, 'w') as fw:
            fw.truncate()
            fw.write(str(argyle_and_classic_curr_line))


def record_whole_problem_performance(num_iter: int=1,
                                     timeout=5,
                                     smt_log_dir="./problems_instances/whole_problem_records/smt2_files/",
                                     time_record_dir: str = ""
                                     ):
    seed = time.time()

    time_record_whole_problem_dir = os.path.join(time_record_dir,"whole_problem_time_records")
    if not os.path.exists(time_record_whole_problem_dir):
        print(f"Provided directory does not exist, creating new directory: {time_record_whole_problem_dir}")
        os.makedirs(time_record_whole_problem_dir)
    store_time_comparison_path = os.path.join(time_record_whole_problem_dir,"time.txt")

    # Iterate through all possible condition combinations
    for index in range(num_iter):
        print(f'Solving the {index}th problem')
        store_result_dict = {}
        empty_list = [0 for i in range(9) for j in range(9)]

        store_result_dict["problem"] = {
            "grid": str(empty_list)
        }
        # iterate through possible combinations
        for condition in FULL_CONDITIONS:
            for single_condition in FULL_CONDITIONS:
                if single_condition not in store_result_dict:
                    store_result_dict[single_condition] = {}
                if "smt_path" not in store_result_dict[single_condition]:
                    # generate the smt file corresponding to the problem
                    s_full = Sudoku.Sudoku(empty_list, *condition, seed=seed)
                    single_condition_smt_path = s_full.gen_full_and_write_smt2_to_file(smt_dir=smt_log_dir)  # write
                    store_result_dict[single_condition]["smt_path"] = single_condition_smt_path
                else:
                    single_condition_smt_path = store_result_dict[single_condition]["smt_path"]

                # launch multiple solvesr and record to dict
                store_result_dict[single_condition] = run_solvers(smt2_file=single_condition_smt_path,time_out=timeout)

                # sql timelog

                # sql db time record file
                db_dir = os.path.join(time_record_whole_problem_dir,"time.db")
                table_name = "example"  # TODO: change into a parameter

                wrapper = Sql_db_wrapper(path=db_dir, table_name=table_name, columns={"ID": "INTEGER PRIMARY KEY",
                                                                                     #
                                                                                     "problem_instance": "INTEGER",
                                                                                     "problem_grid": "TEXT",
                                                                                     "problem_index": "TEXT",
                                                                                     "problem_tryval": "INTEGER",
                                                                                     "problem_assert_equals": "BOOL",
                                                                                     "problem_is_sat": "TEXT",
                                                                                     #
                                                                                     "cond_is_classic": "BOOL",
                                                                                     "cond_is_distinct": "BOOL",
                                                                                     "cond_is_per_col": "BOOL",
                                                                                     "cond_is_no_num": "BOOL",
                                                                                     "cond_is_profill": "BOOL",
                                                                                     #
                                                                                     "res_time_z3": "FLOAT",
                                                                                     "res_timeout_z3": "BOOL"})

                for key in store_result_dict.keys():
                    if isinstance(key, str):
                        continue
                    # column 0 is the Primary Key.
                    wrapper[1:].append([
                        index,
                        store_result_dict["problem"]["grid"],
                        str(store_result_dict["problem"]["index"])[1:-1],
                        store_result_dict["problem"]['try_Val'],
                        store_result_dict["problem"]["assert_equals"],
                        store_result_dict["problem"]["is_sat"],
                        key[0],
                        key[1],
                        key[2],
                        key[3],
                        key[4],
                        store_result_dict[key]['z3'][0],
                        store_result_dict[key]['z3'][1],
                    ])
                del wrapper

                # txt time log
                with open(store_time_comparison_path, 'a+') as fw:
                    fw.write(str(store_result_dict) + '\n')
    # TODO: @sj Cannot implement this for holes

            # Generate holes sudoku, to be implemented
            #
            # s_holes = Sudoku(s_full._nums, *condition, seed=seed)
            # smt_str_holes = s_holes.generate_holes_smt2(os.path.join(hard_smt_dir, f"holes_{to_str(condition)}.smt2"))
            #
            # # Record the performance of different solvers for generating holes sudoku
            # for SOLVER in SOLVER_LIST:
            #     holes_time, holes_timeout, holes_result = solve_with_solver(SOLVER, smt_str_holes, time_out=timeout)
            #     # Record the results
            #     # ...


def load_and_alternative_solve_hard(num_iter:int=0):
    """
    One instances take approximately 1 minute
    """
    time_record_dir = "./time-record/particular_hard_instance_time_record/"
    currline_path = "./problems_instances/particular_hard_instances_records/txt_files/curr_instance_line.txt"
    hard_instances_txt_log_dir = "./problems_instances/particular_hard_instances_records/txt_files/"
    # load_and_alternative_solve(hard_instances_time_record_dir, is_classic=True, num_iter=10,
    #                            currline_path=alternative_solve_curr_line_path, timeout=TIME_OUT)
    print(f'loading and solving for {num_iter} hard instances (across all solvers and all conditions)\n'
          f'{"-" * num_iter}')
    for i in range(num_iter):
        load_and_alternative_solve_hard_once(hard_instances_txt_log_dir=hard_instances_txt_log_dir, time_record_dir=time_record_dir, is_classic=False, num_iter=1,
                                    currline_path=currline_path, timeout=TIME_OUT)
        print('-',end='')

def run_experiment(num_iter=1):
    # dictionary of file paths to feed into `run_experiment_once`
    dct = {"curr_line_path": './sudoku_database/curr_line_of_solving_full_sudokus.txt',
           "classic_full_path": './sudoku_database/classic_full_sudokus.txt',
           "argyle_full_path": './sudoku_database/argyle_full_sudokus.txt',
           "classic_holes_path": './sudoku_database/classic_holes_sudokus.txt',
           "argyle_holes_path": "./sudoku_database/argyle_holes_sudokus.txt",
           "hard_sudoku_dir": "./problems_instances/particular_hard_instances_records/txt_files/",
           "time_record_dir": './time-record/whole_problem_time_records/',
           "hard_smt_log_dir": './problems_instances/particular_hard_instances_records/smt2_files/'}
    for i in range(num_iter):
        run_experiment_once(False,
                            **dct
                            )

if __name__ == '__main__':
    start_time = time.time()
    TIME_OUT = 5

    run_experiment(1)  # about 5 minutes per experiment
    load_and_alternative_solve_hard(1) # about 30-60 seconds per instance
    end_time = time.time()
    print(f"Process Complete. Total time taken: {end_time-start_time}")
