#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
整合脚本：
1) 调用 Bacteria_to_engineered_bacteriophage.py 预测细菌基因组中的溶源性噬菌体。
2) 对每个预测到的噬菌体（.gbk 文件）调用 phage_design.py 进行工程化改造。
输出改造成果到 .../prophage/engineering_bacteriophages/ 目录下。
"""

import os
import sys
import argparse
import subprocess

def main():
    parser = argparse.ArgumentParser(description="一键运行细菌溶源性噬菌体预测 + 噬菌体工程化改造。")
    parser.add_argument(
        "--file_path", 
        required=True, 
        help="输入细菌的GBK文件路径，用于溶源性噬菌体预测。"
    )
    parser.add_argument(
        "--output_path", 
        required=True, 
        help="输出结果的目录路径。"
    )
    args = parser.parse_args()

    # ---------------------------
    # 第一步：细菌溶源性噬菌体预测
    # ---------------------------
    print(f"[1/2] 运行 Bacteria_to_engineered_bacteriophage.py，预测溶源性噬菌体...")
    cmd_bacteria = [
        sys.executable,  # Python可执行文件
        "Bacteria_to_engineered_bacteriophage.py",
        "--file_path", args.file_path,
        "--output_path", args.output_path
    ]
    try:
        subprocess.run(cmd_bacteria, check=True)
    except subprocess.CalledProcessError as e:
        print(f"错误：运行 Bacteria_to_engineered_bacteriophage.py 失败：{e}")
        sys.exit(1)

    # ---------------------------
    # 第二步：对预测到的噬菌体进行工程化改造
    # ---------------------------
    # 根据输入文件名获取它的“basename”（去掉后缀）
    input_basename = os.path.splitext(os.path.basename(args.file_path))[0]
    
    # Bacteria_to_engineered_bacteriophage.py 的输出结构
    # <output_path>/
    #   └── <input_basename>_bactrial/
    #       └── prophage/
    #           └── <input_basename>/
    #               ├── prophiNC_.../
    #               │   ├── ...
    #               │   └── something.gbk
    #               ├── ...
    # 我们需要在 <input_basename>_bactrial/prophage/<input_basename>/ 下寻找 prophi* 子文件夹，
    # 并在每个子文件夹中找到 .gbk 文件，交给 phage_design.py 进行工程化改造。

    # 1) 拼装 prophage 根目录
    prophage_root = os.path.join(
        args.output_path, 
        f"{input_basename}_bactrial", 
        "prophage", 
        input_basename
    )
    
    # 若此目录不存在，说明第一步可能没有成功，或者没有找到噬菌体
    if not os.path.isdir(prophage_root):
        print(f"警告：未找到预期的目录 {prophage_root}，可能没有检测到噬菌体或第一步执行失败。")
        return
    
    # 2) 准备工程化改造的输出目录
    #    放在同级的 prophage/ 下，目录名为 engineering_bacteriophages
    engineering_output_dir = os.path.join(
        args.output_path,
        f"{input_basename}_bactrial",
        "prophage",
        "engineering_bacteriophages"
    )
    os.makedirs(engineering_output_dir, exist_ok=True)

    # 3) 遍历 prophiNC_... 子目录，并找出其中的 .gbk 文件
    for item in os.listdir(prophage_root):
        prophi_folder = os.path.join(prophage_root, item)
        if os.path.isdir(prophi_folder) and item.startswith("prophi"):
            # 在每个 prophiNC_... 文件夹中查找所有 .gbk 文件
            for filename in os.listdir(prophi_folder):
                if filename.lower().endswith(".gbk"):
                    gbk_file = os.path.join(prophi_folder, filename)
                    print(f"[2/2] 对 {gbk_file} 进行工程化改造...")
                    # 保证phage_design.py加入环境变量
                    cmd_phage = [
                        
                        "phage_design.py",
                        "-input_path", gbk_file,
                        "-output_dir", engineering_output_dir
                    ]
                    try:
                        subprocess.run(cmd_phage, check=True)
                    except subprocess.CalledProcessError as e:
                        print(f"错误：运行 phage_design.py 失败：{e}")
                        # 根据需求，你可以选择继续处理下一个文件，或直接退出
                        # 这里我们选择打印错误，然后继续处理下一个文件
                        continue
    
    print("所有步骤完成。")

if __name__ == "__main__":
    main()

