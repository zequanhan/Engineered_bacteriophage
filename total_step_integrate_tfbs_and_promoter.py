from Bio import SeqIO, motifs
import matplotlib.patches as patches
import threading
import subprocess
from Bio.Seq import Seq
import pandas as pd
import os
import matplotlib.pyplot as plt
import logomaker
import tempfile
import sys

#o.chdir('/home/hanzequan/DPProm/DPProm')
#sys.path.append('/home/hanzequan/test_bectiral/operator_recongize/blastp_find_motif')
from needle_and_blasp_find_new_genome_tfbs import *
#from prokka import run_prokka
from DPProm import DPProm_main


def run_needle(seq1, seq2):
    """
    Use the needle algorithm to merge sequences.

    Parameters:
    seq1 (str): The first DNA sequence.
    seq2 (str): The second DNA sequence.

    Returns:
    DataFrame: DataFrame containing alignment details with the highest score.
    """
    seq1_rc = str(Seq(seq1).reverse_complement())
    results = {}
    sequences_to_test = [(seq1, "original"), (seq1_rc, "reverse complement")]

    for sequence, label in sequences_to_test:
        with tempfile.NamedTemporaryFile('w+', delete=False) as temp_seq1, \
                tempfile.NamedTemporaryFile('w+', delete=False) as temp_seq2:
            temp_seq1.write(f">seq1\n{sequence}\n")
            temp_seq2.write(f">seq2\n{seq2}\n")
            temp_seq1.flush()
            temp_seq2.flush()

            output_path = tempfile.NamedTemporaryFile('w+', delete=False).name
            command = [
                '/home/hanzequan/test_bectiral/EMBOSS/emboss/needle',
                '-asequence', temp_seq1.name,
                '-bsequence', temp_seq2.name,
                '-gapopen', '10',
                '-gapextend', '0.5',
                '-outfile', output_path,
                '-auto', 'yes'
            ]

            try:
                subprocess.run(command, check=True)
                details = extract_alignment_details(output_path)
                if details:
                    results[label] = details
            except subprocess.CalledProcessError as e:
                print(f"Error running needle with {label}: {e}")
            except FileNotFoundError as e:
                print(f"Error: Output file not found with {label}: {e}")

    if results:
        max_label = max(results, key=lambda x: results[x].get('Score', float('-inf')))
        return pd.DataFrame([results[max_label]])
    else:
        return pd.DataFrame()


class GenomeAnalyzer:
    def __init__(self, gbk_path, fasta_path, output_dir, pwm_35=None, pwm_10=None, window_size_35=6, window_size_10=6,
                 gap_range=(14, 20)):
        """
        Initializes the GenomeAnalyzer class with the necessary parameters.

        Parameters:
        gbk_path (str): Path to the GenBank file.
        fasta_path (str): Path to the FASTA file.
        output_dir (str): Directory to save the output files.
        pwm_35 (dict): PWM for the -35 region (default is None).
        pwm_10 (dict): PWM for the -10 region (default is None).
        window_size_35 (int): Window size for the -35 region (default is 6).
        window_size_10 (int): Window size for the -10 region (default is 6).
        gap_range (tuple): Range of gaps between -35 and -10 regions (default is (14, 20)).
        """
        self.gbk_path = gbk_path
        self.fasta_path = fasta_path
        self.output_dir = output_dir
        self.window_size_35 = window_size_35
        self.window_size_10 = window_size_10
        self.gap_range = gap_range
        self.results = {}
        self.pwm_35 = pwm_35 if pwm_35 is not None else {
            'A': [0.0000, 0.0784, 0.0362, 0.4894, 0.3605, 0.4208],
            'C': [0.1109, 0.0656, 0.0747, 0.2851, 0.3605, 0.0769],
            'G': [0.1267, 0.0181, 0.6192, 0.1041, 0.0000, 0.2225],
            'T': [0.7624, 0.8379, 0.2700, 0.1214, 0.2790, 0.2798]
        }
        self.pwm_10 = pwm_10 if pwm_10 is not None else {
            'A': [0.0097, 1.0000, 0.3363, 0.5335, 0.4963, 0.0781],
            'C': [0.0618, 0.0000, 0.1190, 0.1094, 0.2299, 0.0268],
            'G': [0.1042, 0.0000, 0.0856, 0.1317, 0.1399, 0.0000],
            'T': [0.8244, 0.0000, 0.4591, 0.2254, 0.1339, 0.8951]
        }

    def calculate_pwm_score(self, sequence, pwm):
        """
        Calculates the PWM score for a given DNA sequence using the provided PWM.

        Parameters:
        sequence (str): The DNA sequence to score.
        pwm (dict): The Position Weight Matrix used for scoring.

        Returns:
        float: The total PWM score for the sequence.
        """
        score = 0
        for i, base in enumerate(sequence):
            score += pwm.get(base, [0] * len(sequence))[i]
        return score

    def complement(self, seq):
        """
        Returns the complement of a given DNA sequence.

        Parameters:
        seq (str): DNA sequence to complement.

        Returns:
        str: Complemented DNA sequence.
        """
        complement = {'A': 'T', 'T': 'A', 'C': 'G', 'G': 'C'}
        return ''.join([complement.get(base, base) for base in reversed(seq)])

    def scan_sequence_for_regions_and_create_dataframe(self, full_sequence, pwm_35, pwm_10):
        """
        Scans the full DNA sequence for -35 and -10 regions and creates a DataFrame of the results.

        Parameters:
        full_sequence (str): The full DNA sequence to scan.
        pwm_35 (dict): PWM for the -35 region.
        pwm_10 (dict): PWM for the -10 region.

        Returns:
        DataFrame: A DataFrame containing the -35 and -10 sequences and their total scores.
        """
        data = []
        for i in range(len(full_sequence) - self.window_size_35 + 1):
            window_sequence_35 = full_sequence[i:i + self.window_size_35]
            score_35 = self.calculate_pwm_score(window_sequence_35, pwm_35)
            for gap in range(self.gap_range[0], self.gap_range[1] + 1):
                start_10 = i + self.window_size_35 + gap
                if start_10 + self.window_size_10 <= len(full_sequence):
                    window_sequence_10 = full_sequence[start_10:start_10 + self.window_size_10]
                    score_10 = self.calculate_pwm_score(window_sequence_10, pwm_10)
                    total_score = self.round_score(score_35 + score_10)
                    data.append({
                        "-35 Sequence": window_sequence_35,
                        "-35 Score": self.round_score(score_35),
                        "Start Position -35": i,
                        "-10 Sequence": window_sequence_10,
                        "-10 Score": self.round_score(score_10),
                        "Start Position -10": start_10,
                        "Total Score": total_score
                    })
        df = pd.DataFrame(data)
        return df.sort_values(by="Total Score", ascending=False)

    def round_score(self, score):
        """
        Rounds the given score to two decimal places.

        Parameters:
        score (float): The score to round.

        Returns:
        float: The rounded score.
        """
        return round(score, 2)

    def find_matching_regions(self, predicted_seq, real_seq, strand):
        """
        Finds matching regions between predicted and real sequences.

        Parameters:
        predicted_seq (str): Predicted DNA sequence.
        real_seq (str): Real DNA sequence.
        strand (str): Strand information ('+' or '-').

        Returns:
        list: List of tuples containing start and end positions and strand information.
        str: Complemented real sequence if strand is negative.
        """
        if strand == '-':
            real_seq = self.complement(real_seq)
        return [(i, i + len(real_seq)) for i in range(len(predicted_seq) - len(real_seq) + 1) if
                predicted_seq[i:i + len(real_seq)] == real_seq], real_seq

    def find_overlapping_region_relative(self, predicted_start, predicted_end, real_start, real_end):
        """
        Calculates the relative start and end positions of the overlapping region.

        Parameters:
        predicted_start (int): Start position of the predicted region.
        predicted_end (int): End position of the predicted region.
        real_start (int): Start position of the real region.
        real_end (int): End position of the real region.

        Returns:
        tuple: Relative start and end positions of the overlapping region.
        """
        overlap_start_absolute = max(predicted_start, real_start)
        overlap_end_absolute = min(predicted_end, real_end)
        overlap_start_relative_to_predicted = overlap_start_absolute - predicted_start
        overlap_end_relative_to_predicted = overlap_end_absolute - predicted_start
        return overlap_start_relative_to_predicted, overlap_end_relative_to_predicted

    def find_matching_regions_with_relative_info(self, predicted_seq, predicted_start, predicted_end, real_seq,
                                                 real_start, real_end, strand):
        """
        Finds matching regions between predicted and real sequences with relative position information.

        Parameters:
        predicted_seq (str): Predicted DNA sequence.
        predicted_start (int): Start position of the predicted region.
        predicted_end (int): End position of the predicted region.
        real_seq (str): Real DNA sequence.
        real_start (int): Start position of the real region.
        real_end (int): End position of the real region.
        strand (str): Strand information ('+' or '-').

        Returns:
        list: List of tuples containing relative start and end positions and strand information.
        str: Complemented real sequence if strand is negative.
        """
        overlap_start_relative, overlap_end_relative = self.find_overlapping_region_relative(predicted_start,
                                                                                             predicted_end, real_start,
                                                                                             real_end)
        if strand == '-':
            real_seq = self.complement(real_seq)
        overlapping_seq = predicted_seq[overlap_start_relative:overlap_end_relative + 1]
        return [(overlap_start_relative, overlap_end_relative)], real_seq

    def extract_sequence(self, gbk_path, protein_names):
        """
        Extracts a protein sequence from a GenBank file that matches any of the given protein names.

        Parameters:
        gbk_path (str): Path to the GenBank file.
        protein_names (list): List of protein names to match.

        Returns:
        str: The matching protein sequence, or None if no match is found.
        """
        record = SeqIO.read(gbk_path, "genbank")
        for feature in record.features:
            if feature.type == "CDS" and "product" in feature.qualifiers:
                product_name = feature.qualifiers["product"][0].lower()
                if any(protein_name.lower() in product_name for protein_name in protein_names):
                    return feature.qualifiers["translation"][0]
        return None

    def write_sequences_to_fasta(self, sequences, output_path):
        """
        Writes a list of sequences to a FASTA file.

        Parameters:
        sequences (list): List of sequences to write.
        output_path (str): Path to save the FASTA file.
        """
        with open(output_path, "w") as file:
            for idx, seq in enumerate(sequences):
                file.write(f">protein_{idx}\n{seq}\n")

    def run_blastp(self, query_fasta, db_path, output_path):
        """
        Runs the BLASTP tool to compare the query sequences against a database.

        Parameters:
        query_fasta (str): Path to the query FASTA file.
        db_path (str): Path to the BLAST database.
        output_path (str): Path to save the BLAST output.
        """
        command = [
            'blastp',
            '-query', query_fasta,
            '-db', db_path,
            '-out', output_path,
            '-outfmt', "6 qaccver saccver pident length mismatch gapopen qstart qend sstart send evalue bitscore"
        ]
        subprocess.run(command, check=True)

    def parse_blast_results(self, blast_output):
        """
        Parses the BLASTP output file to extract relevant information.

        Parameters:
        blast_output (str): Path to the BLAST output file.

        Returns:
        dict: A dictionary containing the best BLAST hit information, or None if no hits are found.
        """
        column_names = ["query_accver", "subject_accver", "percentage_identity", "alignment_length", "mismatches",
                        "gap_opens", "query_start", "query_end", "subject_start", "subject_end", "evalue", "bit_score"]
        try:
            df = pd.read_csv(blast_output, sep="\t", names=column_names)
            if not df.empty:
                best_hit = df.iloc[0]
                formatted_acc = best_hit['subject_accver'].split('.')[0]
                protein_name = best_hit['subject_accver']
                evalue = best_hit['evalue']
                return {
                    'Accession': formatted_acc,
                    'E-value': evalue,
                    'Protein Name': protein_name
                }
            else:
                return None
        except Exception as e:
            print(f"Error reading BLAST output: {e}")
            return None

    def create_motif_visualization(self, accession, gbk_path):
        """
        Creates a motif visualization based on the provided accession and GenBank path.

        Parameters:
        accession (str): The accession number.
        gbk_path (str): Path to the GenBank file.
        """
        directories = self.find_directories_with_string(self.output_dir, accession)
        all_motifs_df = pd.DataFrame()
        sequence_count_occurrences = {}
        for directory in directories:
            try:
                meme_df = self.build_motif_matrices(directory, sequence_count_occurrences)
                all_motifs_df = pd.concat([all_motifs_df, meme_df], ignore_index=True)
            except FileNotFoundError as e:
                print(e)

        comparison_results_df = self.run_comparisons_on_motifs(all_motifs_df)
        final_df = comparison_results_df[
            comparison_results_df['State Change'] == comparison_results_df['State Change'].max()]
        best_motif = all_motifs_df[all_motifs_df['Motif'] == self.merge_sequences_based_on_identity(final_df)[
            self.merge_sequences_based_on_identity(final_df).index == 0]['Motif'].iloc[0]]
        sequences = best_motif['Sequence'].to_list()

        min_length = min(len(seq) for seq in sequences)
        sequences_truncated = [seq[:min_length] for seq in sequences]
        sequences_truncated = [Seq(seq) for seq in sequences_truncated]

        m = motifs.create(sequences_truncated)
        pwm = m.counts.normalize(pseudocounts={'A': 0, 'C': 0, 'G': 0, 'T': 0})
        pwm_array = np.array([pwm[nucleotide] for nucleotide in 'ACGT']).T

        results = self.search_tfbs_in_genome(pwm_array, gbk_path)
        processed_sequences = []
        for _, row in results.iterrows():
            sequence = Seq(row['Sequence'])
            if row['Strand'] == '-':
                sequence = sequence.reverse_complement()
            processed_sequences.append(sequence)
        if processed_sequences:
            m = motifs.create(processed_sequences)
            pwm = m.counts.normalize(pseudocounts={'A': 0, 'C': 0, 'G': 0, 'T': 0})
            pwm_df = pd.DataFrame({nucleotide: pwm[nucleotide] for nucleotide in 'ACGT'})
            ic = logomaker.transform_matrix(pwm_df, from_type='probability', to_type='information')

            fig, ax = plt.subplots(figsize=(10, 3))
            logo = logomaker.Logo(ic, ax=ax)
            ax.set_ylabel('bits', fontsize=12)
            ax.set_ylim(bottom=0)
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            ax.yaxis.tick_left()
            plt.show()

        self.results['meme'] = results
        self.results['meme_pwm'] = pwm_df

    def search_tfbs_in_genome(self, pwm, gbk_path):
        """
        Searches for transcription factor binding sites (TFBS) in the genome using the given PWM.

        Parameters:
        pwm (numpy.ndarray): Position weight matrix for the TFBS.
        gbk_path (str): Path to the GenBank file.

        Returns:
        DataFrame: DataFrame containing the TFBS information.
        """

        def find_tfbs(pwm, sequence, top_n=20):
            base_index = {'A': 0, 'C': 1, 'G': 2, 'T': 3}
            L = pwm.shape[0]
            scores = []

            for i in range(len(sequence) - L + 1):
                segment = sequence[i:i + L]
                score = 0
                for j, base in enumerate(segment):
                    if base in base_index:
                        score += pwm[j, base_index[base]]
                    else:
                        score = -np.inf
                        break
                if score != -np.inf:
                    scores.append((+1, i, i + L, score))

            scores.sort(key=lambda x: x[3], reverse=True)
            top_scores = scores[:top_n]
            return top_scores

        record = SeqIO.read(gbk_path, 'genbank')
        sequence = record.seq
        tfbs_sites = find_tfbs(pwm, sequence)

        result_matrix = []
        for site in tfbs_sites:
            strand, start, end, score = site
            result_matrix.append({
                'Sequence': str(sequence[start:end]),
                'Start': start,
                'End': end,
                'Strand': '+' if strand == 1 else '-',
                'Score': score
            })

        result_df = pd.DataFrame(result_matrix)
        return result_df

    def extract_promoters(self, key, dp_prom_path="/home/hanzequan/DPProm/DPProm/"):
        """
        Extracts promoter sequences using DPProm tool and stores the results.

        Parameters:
        key (str): Key to store the results in the class dictionary.
        dp_prom_path (str): Path to the DPProm tool (default is "/home/hanzequan/DPProm/DPProm/").
        """
        seqs, headers = DPProm_main.genome_predict(dp_prom_path, self.gbk_path, self.fasta_path)
        data = []
        for i, header in enumerate(headers):
            parts = header.split()
            promoter_number = parts[1]
            position_info = parts[3].strip('()')
            start, end = map(int, position_info.split('..'))
            score = float(parts[10])
            host = parts[-1]
            sequence = seqs[i]
            if len(sequence) > 28:  # 仅保留序列长度大于28的启动子
                data.append({
                    'promoter_number': promoter_number,
                    'start': start,
                    'end': end,
                    'score': score,
                    'sequence': sequence,
                    'host': host
                })
        df_promoters = pd.DataFrame(data)
        self.results[key] = df_promoters
    def process_meme_results(self):
        """
        Processes the MEME results stored in the class dictionary.
        """
        if 'meme' in self.results:
            meme_results = self.results['meme']
            meme_results.columns = [col.lower() for col in meme_results.columns]
            meme_results['end'] = meme_results['start'] + meme_results['sequence'].apply(len) - 1
            self.results['meme'] = meme_results
    def plot_sequences_with_promoter_regions(self, predicted_seq, real_seq, matching_regions, predicted_index,
                                             real_index, pwm_35, pwm_10):
        """
        Plots the predicted and real sequences with highlighted promoter regions.

        Parameters:
        predicted_seq (str): Predicted DNA sequence.
        real_seq (str): Real DNA sequence.
        matching_regions (list): List of matching regions between predicted and real sequences.
        predicted_index (int): Index of the predicted sequence.
        real_index (int): Index of the real sequence.
        pwm_35 (dict): PWM for the -35 region.
        pwm_10 (dict): PWM for the -10 region.
        """
        fig, ax = plt.subplots(figsize=(len(predicted_seq), 2))
        for i, nucleotide in enumerate(predicted_seq):
            ax.text(i, 1, nucleotide, ha='center', va='center', fontsize=12, color='black')

        for start, end in matching_regions:
            ax.add_patch(patches.Rectangle((start, 0), end - start, 1, color='red', alpha=0.3))

        for start, end in matching_regions:
            for pos in range(start, end):
                ax.text(pos, 0, real_seq[pos - start], ha='center', va='center', fontsize=12, color='white')

        ax.text(0, 1.5, f'Predicted Index: {predicted_index}', ha='left', va='center', fontsize=10, color='black')
        ax.text(0, -0.5, f'Real Index: {real_index}', ha='left', va='center', fontsize=10, color='red')

        df_promoter = self.scan_sequence_for_regions_and_create_dataframe(predicted_seq, pwm_35, pwm_10)
        if not df_promoter.empty:
            top_result = df_promoter.iloc[0]
            ax.add_patch(
                patches.Rectangle((top_result['Start Position -35'], 0.5), self.window_size_35, 0.5, color='blue',
                                  alpha=0.3))
            ax.add_patch(
                patches.Rectangle((top_result['Start Position -10'], 0.5), self.window_size_10, 0.5, color='yellow',
                                  alpha=0.3))


        ax.set_xlim(0, len(predicted_seq))
        ax.set_ylim(-1, 2)


        ax.axis('off')
        plt.tight_layout()
        save_path = os.path.join(self.output_dir, f"sequence_match_{predicted_index}_{real_index}.png")
        #plt.savefig(save_path)
        #plt.show()
    def plot_matching_sequences(self, meme_results, df_promoters, pwm_35, pwm_10):
        used_predicted_indices = set()
        used_real_indices = set()
        for real_index, real in meme_results.iterrows():
            if real_index in used_real_indices:
                continue
            for predicted_index, predicted in df_promoters.iterrows():
                if predicted_index in used_predicted_indices:
                    continue
                if (predicted['start'] <= real['end']) and (predicted['end'] >= real['start']):
                    predicted_seq = predicted['sequence']
                    real_seq = real['sequence']
                    strand = real['strand']

                    matching_regions, real_seq = self.find_matching_regions_with_relative_info(predicted_seq, predicted['start'], predicted['end'], real_seq, real['start'], real['end'], strand)
                    if matching_regions:
                        used_predicted_indices.add(predicted_index)
                        used_real_indices.add(real_index)
                        self.plot_sequences_with_promoter_regions(
                            predicted_seq, real_seq, matching_regions,
                            predicted_index, real_index, pwm_35, pwm_10
                        )
                        break
    def analyze_genome(self):
        """
        Analyzes the genome to identify motifs, extract promoters, and plot matching sequences.

        Returns:
        tuple: MEME results, promoter data, and PWM DataFrame.
        """
        protein_names = [
            'repressor', 'transcriptional regulator', 'immunity repressor',
            'transcriptional repressor', 'Cro/CI family transcriptional regulator',
            'Hxr', 'CI protein', 'CII-like transcriptional activator'
        ]
        #query_fasta = "/home/public_new/dowlond_phage/query_proteins.fasta"
        #db_path = "/home/public_new/dowlond_phage/all_phage_tree/blast_db/blast_db"
        #db_path = "/home/public_new/dowlond_phage/blast_ncbi_repressor"
        #blast_output = "/home/public_new/dowlond_phage/blast_results.tsv"
        current_dir = os.path.dirname(os.path.abspath(__file__))

        # 构建相对路径（假设脚本同级目录下有 blast_ncbi_repressor 和 blast_results）
        db_path = os.path.join(current_dir, "blast_ncbi_repressor/combined_proteins_db")
        query_fasta = os.path.join(current_dir, "blast_results", "query_proteins.fasta")
        blast_output = os.path.join(current_dir, "blast_results", "blast_results.tsv")

        sequence = self.extract_sequence(self.gbk_path, protein_names)
        if sequence:
            self.write_sequences_to_fasta([sequence], query_fasta)
            self.run_blastp(query_fasta, db_path, blast_output)
            result = self.parse_blast_results(blast_output)
            if result:
                accession = result['Accession']
                print(f"Accession: {accession}, E-value: {result['E-value']}, Protein Name: {result['Protein Name']}")

                thread_meme = threading.Thread(target=self.create_motif_visualization, args=(accession, self.gbk_path))
                thread_promoters = threading.Thread(target=self.extract_promoters, args=('promoters',))

                thread_meme.start()
                thread_promoters.start()

                thread_meme.join()
                thread_promoters.join()
                self.process_meme_results()

                meme_results = self.results.get('meme')
                df_promoters = self.results.get('promoters')
                pwm_df = self.results.get('meme_pwm')

                self.plot_matching_sequences(meme_results, df_promoters, self.pwm_35, self.pwm_10)
                return meme_results, df_promoters, pwm_df
            else:
                print("No BLAST hits found or failed to parse BLAST output.")
        else:
            print("No matching sequence found in the GenBank file.")
        return None, None, None

    def find_directories_with_string(self, root_directory, target_string, file_extension=".txt"):
        """
        Finds directories containing files with the specified string.

        Parameters:
        root_directory (str): Root directory to search.
        target_string (str): String to search for in files.
        file_extension (str): File extension to filter by (default is ".txt").

        Returns:
        set: Set of directories containing files with the specified string.
        """
        root_directory = '/home/hanzequan/test_bectiral/operator_recongize/all_tree'
        directories = set()
        for root, dirs, files in os.walk(root_directory):
            for file in files:
                if file.endswith(file_extension):
                    file_path = os.path.join(root, file)
                    with open(file_path, 'r', encoding='utf-8') as f:
                        if target_string in f.read():
                            directories.add(root)
        return directories

    def build_motif_matrices(self, directory, sequence_count_occurrences):
        """
        Builds motif matrices from MEME output files in the specified directory.

        Parameters:
        directory (str): Directory to search for MEME output files.
        sequence_count_occurrences (dict): Dictionary to track sequence occurrences.

        Returns:
        DataFrame: DataFrame containing motif data.
        """
        all_motifs_data = pd.DataFrame()
        found_xml = False

        for root, dirs, files in os.walk(directory):
            for file in files:
                if file == 'meme.xml':
                    found_xml = True
                    xml_file = os.path.join(root, file)
                    txt_file = os.path.join(os.path.dirname(root), os.path.basename(root) + '.txt')

                    try:
                        with open(txt_file, 'r') as txt:
                            for line in txt.readlines():
                                line = line.strip()
                                if line:
                                    sequence_ids = line.split(',')
                                    sequence_count = len(sequence_ids)
                                    if sequence_count in sequence_count_occurrences:
                                        sequence_count_occurrences[sequence_count] += 1
                                    else:
                                        sequence_count_occurrences[sequence_count] = 0
                    except FileNotFoundError:
                        print(f"Warning: Corresponding text file not found: {txt_file}")

                    with open(xml_file) as f:
                        meme_record = motifs.parse(f, "meme")

                    motif_index = 1
                    for motif in meme_record:
                        sequences = [Seq(str(instance)) for instance in motif.instances]
                        motifs_data = []
                        for instance in motif.instances:
                            sequence_name = instance.sequence_name
                            id = motif.id
                            consensus = motif.name
                            e_value = motif.evalue
                            num_occurrences = len(motif.instances)
                            suffix = f".{sequence_count_occurrences[sequence_count]}" if sequence_count_occurrences[
                                                                                             sequence_count] > 0 else ""
                            motif_data = {
                                "Number": f"{sequence_count}{suffix}",
                                "Layer": id,
                                "Strand": instance.strand,
                                "Start": instance.start,
                                "p-value": instance.pvalue,
                                "e-value": e_value,
                                "Sequence": str(instance),
                                "Motif": consensus
                            }
                            motifs_data.append(motif_data)
                        if motifs_data:
                            motifs_df = pd.DataFrame(motifs_data)
                            all_motifs_data = pd.concat([all_motifs_data, motifs_df], ignore_index=True)
                        motif_index += 1

        if not found_xml:
            raise FileNotFoundError(f"No MEME output file found in directory {directory} or its subdirectories.")

        return all_motifs_data

    def run_comparisons_on_motifs(self, df):
        """
        Runs comparisons on motifs using the needle algorithm.

        Parameters:
        df (DataFrame): DataFrame containing motif data.

        Returns:
        DataFrame: DataFrame containing comparison results.
        """
        first_motifs = {}
        unique_numbers = df['Number'].unique()

        for number in unique_numbers:
            for layer in ['motif_1', 'motif_2', 'motif_3']:
                if not df[(df['Number'] == number) & (df['Layer'] == layer)].empty:
                    motif = df[(df['Number'] == number) & (df['Layer'] == layer)]['Motif'].iloc[0]
                    first_motifs[motif] = 0

        results_list = []

        for motif1 in first_motifs.keys():
            for motif2 in first_motifs.keys():
                if motif1 != motif2:
                    result_df = run_needle(motif1, motif2)

                    if not result_df.empty:
                        max_identity = float(result_df['Identity'][0][-1])
                        if max_identity > 70:
                            first_motifs[motif1] += 1
                        for _, row in result_df.iterrows():
                            row['Original Motif'] = motif1
                            row['Target Motif'] = motif2
                            row['State Change'] = first_motifs[motif1]
                            results_list.append(row.to_dict())
        return pd.DataFrame(results_list)

    def merge_sequences_based_on_identity(self, final_df):
        """
        Merges sequences based on their identity from the comparison results.

        Parameters:
        final_df (DataFrame): DataFrame containing final comparison results.

        Returns:
        DataFrame: DataFrame containing merged sequences and their final states.
        """
        motif_counts = final_df['Original Motif'].value_counts().to_dict()
        motifs = list(motif_counts.keys())

        motif_states = {motif: count for motif, count in motif_counts.items()}

        for i, motif1 in enumerate(motifs):
            for motif2 in motifs[i + 1:]:
                if motif1 != motif2 and motif1 in motif_states and motif2 in motif_states:
                    result_df = run_needle(motif1, motif2)
                    if not result_df.empty:
                        max_identity = float(result_df['Identity'][0][-1])
                        if max_identity > 70:
                            larger_motif = motif1 if motif_states[motif1] >= motif_states[motif2] else motif2
                            smaller_motif = motif2 if motif1 == larger_motif else motif1
                            motif_states[larger_motif] += motif_states.pop(smaller_motif, 0)

        final_results = [{'Motif': motif, 'Final State': state} for motif, state in motif_states.items()]
        return pd.DataFrame(final_results)

