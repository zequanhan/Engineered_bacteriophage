#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import time
import subprocess
from Bio import SeqIO
import numpy as np
import sys
import argparse
# ==============
# 把原来的绝对路径替换为相对路径
# ==============
dbscan_swa_script = "DBSCAN-SWA/bin/dbscan-swa.py"
depht_executable  = "depht/run_depht.py"

# 其它脚本如果没变，就不再赘述
# 比如你还有 DPProm_main、generate_result, total_step_integrate_tfbs_and_promoter 的导入等
#current_dir = os.path.dirname(os.path.abspath(__file__))
#sys.path.append(current_dir)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# 将 total_step 文件夹添加到 Python 的搜索路径，以便 import
TOTAL_STEP_DIR = os.path.join(SCRIPT_DIR, 'total_step')
if TOTAL_STEP_DIR not in os.sys.path:
    os.sys.path.append(TOTAL_STEP_DIR)

from generate_result import *
from total_step_integrate_tfbs_and_promoter import GenomeAnalyzer
DBSCAN_SWA_SCRIPT = os.path.join(SCRIPT_DIR, 'DBSCAN-SWA', 'bin', 'dbscan-swa.py')
DEPHT_EXECUTABLE  = os.path.join(SCRIPT_DIR, 'depht', 'depht')  # 或者你的depht可执行文件名称
DPPROM_DIR        = os.path.join(SCRIPT_DIR, 'DPProm')          # DPProm的安装或核心目录
def ensure_directory_exists(directory_path):
    if not os.path.exists(directory_path):
        os.makedirs(directory_path)

def run_dbscan_swa(input_file, output_dir):
    cmd = [
        "python3",
        dbscan_swa_script,
        "--input", input_file,
        "--out", output_dir
    ]
    subprocess.run(cmd, check=True)

def run_depht_command(gbk_file_path, output_path, summary_file_path, model="Mycobacterium", verbose=True):
    """
    原本你用的depht_executable是 /home/.../depht
    现在用同目录下的 depht/__main__.py
    """
    command = [
        "python3",
        depht_executable, 
        gbk_file_path, 
        output_path, 
        summary_file_path,
        "--model", 
        model
    ]
    if verbose:
        command.append("-v")
    subprocess.run(command, check=True)
def run_DPProm(storage_path, depht_output_folder, dpprom_output_folder):
    ensure_directory_exists(depht_output_folder)
    ensure_directory_exists(dpprom_output_folder)
    
    for subdir in os.listdir(depht_output_folder):
        subdir_path = os.path.join(depht_output_folder, subdir)
        if os.path.isdir(subdir_path):
            gbk_files = [os.path.join(subdir_path, f) for f in os.listdir(subdir_path) if f.endswith('.gbk')]
            fasta_files = [os.path.join(subdir_path, f) for f in os.listdir(subdir_path) if f.endswith('.fasta')]

            for gbk_file_path, fasta_file_path in zip(gbk_files, fasta_files):
                print(f"Analyzing: {gbk_file_path} and {fasta_file_path}")
                output_path = os.path.join(dpprom_output_folder, os.path.basename(gbk_file_path).replace('.gbk', ''))
                ensure_directory_exists(output_path)

                # 注意，此处我们依赖于从 total_step_import_xxx
                genome_analyzer = GenomeAnalyzer(gbk_file_path, fasta_file_path, output_path)
                meme_results, df_promoters, pwm_df = genome_analyzer.analyze_genome()

                if meme_results is None:
                    print(f"Skipping {gbk_file_path} and {fasta_file_path} due to None results.")
                    continue

                analyze_tfbs_modification(meme_results, df_promoters, pwm_df, gbk_file_path, output_path)

def time_it(func):
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        duration = end_time - start_time
        print(f"{func.__name__} ran in: {duration} seconds")
        return result
    return wrapper

@time_it
def main(file_path, output_path):
    # 解析原始文件路径和文件名
    dir_path = os.path.dirname(file_path)
    original_basename = os.path.basename(file_path)
    first_part = original_basename.split('.')[0]
    extension = original_basename.split('.')[-1]
    
    # 新的文件名保持不变
    new_basename = first_part + '.' + extension
    new_filepath = os.path.join(dir_path, new_basename)
    
    # 重命名文件（如果新文件名与原文件名相同，这步可以省略）
    if file_path != new_filepath:
        os.rename(file_path, new_filepath)
        print(f"文件已重命名为: {new_filepath}")
    else:
        print("文件名无需重命名。")
    
    # 设置路径参数（基于指定的输出路径）
    # 将输出文件夹名称设为输入文件名加上 '_bactrial'
    output_folder_name = first_part + '_bactrial'
    dbscan_output_folder = os.path.join(output_path, output_folder_name)
    
    # 将 depht_output_folder 改为 'prophage'
    depht_output_folder  = os.path.join(dbscan_output_folder, 'prophage')
    
    # 其他输出文件夹保持不变
    #prokka_genome_folder = os.path.join(dbscan_output_folder, "prokka_genomes")
    #prokka_output_folder = os.path.join(dbscan_output_folder, "prokka_output")
    dpprom_output_folder = os.path.join(dbscan_output_folder, "dpprom_output")
    dpprom_storage_path  = DPPROM_DIR  # 直接指向上面定义好的 DPPROM_DIR

    # 确保输出文件夹存在
    for d in [dbscan_output_folder, dpprom_output_folder, depht_output_folder]:
        ensure_directory_exists(d)

    print('步骤1: 运行dbscan-swa.py')
    run_dbscan_swa(new_filepath, dbscan_output_folder)

    print('步骤2: 运行depht')
    run_depht_command(
        new_filepath,
        depht_output_folder,
        os.path.join(dbscan_output_folder, 'bac_DBSCAN-SWA_prophage_summary.txt')
    )

# =====================================
# 命令行入口
# =====================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="处理细菌基因组文件并生成工程化噬菌体。")
    parser.add_argument(
        '--file_path',
        type=str,
        required=True,
        help='输入的GBK文件路径。'
    )
    parser.add_argument(
        '--output_path',
        type=str,
        required=True,
        help='输出结果的目录路径。'
    )

    args = parser.parse_args()

    gbk_filepath = args.file_path
    output_dir = args.output_path

    # 验证输入文件是否存在
    if not os.path.isfile(gbk_filepath):
        print(f"错误: 输入文件 '{gbk_filepath}' 不存在。")
        sys.exit(1)

    # 验证输出路径是否存在，如果不存在则创建
    ensure_directory_exists(output_dir)

    main(gbk_filepath, output_dir)

