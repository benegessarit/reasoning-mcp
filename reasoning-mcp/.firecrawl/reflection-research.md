HTML conversions [sometimes display errors](https://info.dev.arxiv.org/about/accessibility_html_error_messages.html) due to content that did not convert correctly from the source. This paper uses the following packages that are not yet supported by the HTML conversion tool. Feedback on these issues are not necessary; they are known and are being worked on.

- failed: tabularray.sty
- failed: tabularray.sty

Authors: achieve the best HTML results from your LaTeX submissions by following these [best practices](https://info.arxiv.org/help/submit_latex_best_practices.html).

[License: CC BY 4.0](https://info.arxiv.org/help/license/index.html#licenses-available)

arXiv:2601.12720v1 \[cs.AI\] 19 Jan 2026

# Teaching Large Reasoning Models Effective Reflection

Report issue for preceding element

Hanbin Wang1,
Jingwei Song211footnotemark: 1,
Jinpeng Li3,
Qi Zhu3,

Fei Mi3, Ganqu Cui4,
Yasheng Wang, Lifeng Shang3

1Peking University 2The University of Hong Kong

3Huawei Technologies 4Shanghai AI Lab
Equal contribution.Corresponding author.

Report issue for preceding element

###### Abstract

Report issue for preceding element

Large Reasoning Models (LRMs) have recently shown impressive performance on complex reasoning tasks, often by engaging in self-reflective behaviors such as self-critique and backtracking. However, not all reflections are beneficial—many are superficial, offering little to no improvement over the original answer and incurring computation overhead. In this paper, we identify and address the problem of superficial reflection in LRMs. We first propose Self-Critique Fine-Tuning (SCFT), a training framework that enhances the model’s reflective reasoning ability using only self-generated critiques. SCFT prompts models to critique their own outputs, filters high-quality critiques through rejection sampling, and fine-tunes the model using a critique-based objective. Building on this strong foundation, we further introduce Reinforcement Learning with Effective Reflection Rewards (RLERR). RLERR leverages the high-quality reflections initialized by SCFT to construct reward signals, guiding the model to internalize the self-correction process via reinforcement learning. Experiments on two challenging benchmarks, AIME2024 and AIME2025, show that SCFT and RLERR significantly improve both reasoning accuracy and reflection quality, outperforming state-of-the-art baselines.
All data and codes are available at [https://github.com/wanghanbinpanda/SCFT](https://github.com/wanghanbinpanda/SCFT "").

Report issue for preceding element

Teaching Large Reasoning Models Effective Reflection

Report issue for preceding element

Hanbin Wang1††thanks: Equal contribution.,
Jingwei Song211footnotemark: 1,
Jinpeng Li3††thanks: Corresponding author.,
Qi Zhu3,Fei Mi3, Ganqu Cui4,
Yasheng Wang, Lifeng Shang31Peking University 2The University of Hong Kong3Huawei Technologies 4Shanghai AI Lab

Report issue for preceding element

## 1 Introduction

Report issue for preceding element![Refer to caption](https://arxiv.org/html/2601.12720v1/x1.png)Figure 1: Total number of reflections in correct and incorrect responses on AIME2024. The blue and grey bars respectively show the total occurrences of reflection keywords in correct and incorrect responses. The Effective Reflection Ratio (ERR) is the proportion of reflection keywords in the correct responses, which is defined in Section [3.1](https://arxiv.org/html/2601.12720v1#S3.SS1 "3.1 Effective Reflection ‣ 3 Methodology ‣ Teaching Large Reasoning Models Effective Reflection"). DS represents DeepSeek. Overall, the model is facing serious problems of ineffective reflection.Report issue for preceding element

Recently, Large Reasoning Models (LRMs) such as DeepSeek-R1 DeepSeek-AI et al. ( [2025](https://arxiv.org/html/2601.12720v1#bib.bib3 "DeepSeek-r1: incentivizing reasoning capability in llms via reinforcement learning")) and OpenAI o1 OpenAI et al. ( [2024](https://arxiv.org/html/2601.12720v1#bib.bib10 "OpenAI o1 system card")) have demonstrated outstanding performance in solving complex reasoning tasks across domains such as mathematics, science, and programming. A key factor behind these advancements is the incorporation of reinforcement learning with verifiable rewards Zeng et al. ( [2025](https://arxiv.org/html/2601.12720v1#bib.bib32 "SimpleRL-zoo: investigating and taming zero reinforcement learning for open base models in the wild")); Cui et al. ( [2025](https://arxiv.org/html/2601.12720v1#bib.bib11 "Process reinforcement through implicit rewards")), these models perform long Chain-of-Thought (CoT) Wei et al. ( [2022](https://arxiv.org/html/2601.12720v1#bib.bib4 "Chain-of-thought prompting elicits reasoning in large language models")) reasoning, engaging in detailed thinking before arriving at the final answer Team et al. ( [2025](https://arxiv.org/html/2601.12720v1#bib.bib6 "Kimi k1.5: scaling reinforcement learning with llms")); Muennighoff et al. ( [2025](https://arxiv.org/html/2601.12720v1#bib.bib5 "S1: simple test-time scaling")); Ye et al. ( [2025](https://arxiv.org/html/2601.12720v1#bib.bib21 "LIMO: less is more for reasoning")).

Report issue for preceding element

With the growing complexity of these reasoning traces, researchers have turned their attention to the thinking patterns that emerge within LRMsLiu et al. ( [2025](https://arxiv.org/html/2601.12720v1#bib.bib1 "There may not be aha moment in r1-zero-like training — a pilot study")); Wen et al. ( [2025b](https://arxiv.org/html/2601.12720v1#bib.bib27 "ThinkPatterns-21k: a systematic study on the impact of thinking patterns in llms")); Gandhi et al. ( [2025](https://arxiv.org/html/2601.12720v1#bib.bib13 "Cognitive behaviors that enable self-improving reasoners, or, four habits of highly effective stars")).
These studies reveal that LRMs exhibit a variety of reflective behaviors such as self-critique, verification, and backtracking—behaviors often associated with metacognition and expert reasoning. While such capabilities are desirable in principle, empirical evidence suggests that not all reflections are helpful (Figure [1](https://arxiv.org/html/2601.12720v1#S1.F1 "Figure 1 ‣ 1 Introduction ‣ Teaching Large Reasoning Models Effective Reflection")). Many reflections fail to lead to substantial answer improvements, and sometimes even introduce irrelevant or redundant information. We refer to this phenomenon as superficial reflection—a pattern of reevaluation that does not result in meaningful revision or better task performance. Superficial reflections not only undermine the effectiveness of reflection-based reasoning but also inflate inference cost and latency Liu et al. ( [2025](https://arxiv.org/html/2601.12720v1#bib.bib1 "There may not be aha moment in r1-zero-like training — a pilot study")).

Report issue for preceding element

To encourage more effective reflection, Critique Fine-Tuning (CFT) has been proposed as a promising training paradigm that fine-tunes models with critiques as supervision signals Wang et al. ( [2025](https://arxiv.org/html/2601.12720v1#bib.bib17 "Critique fine-tuning: learning to critique is more effective than learning to imitate")). However, prior CFT approaches typically depend on high-quality critique annotations from stronger external models or human experts—resources that are expensive and difficult to scaleLan et al. ( [2024](https://arxiv.org/html/2601.12720v1#bib.bib14 "Training language models to critique with multi-agent feedback")); Xie et al. ( [2025](https://arxiv.org/html/2601.12720v1#bib.bib15 "Teaching language models to critique via reinforcement learning")); Xi et al. ( [2024](https://arxiv.org/html/2601.12720v1#bib.bib16 "Enhancing llm reasoning via critique models with test-time and training-time supervision")). In addition, previous attempts to use self-generated critiques for training have struggled to produce gains, due to the noisy and low-quality nature of these critiquesWang et al. ( [2025](https://arxiv.org/html/2601.12720v1#bib.bib17 "Critique fine-tuning: learning to critique is more effective than learning to imitate")). Furthermore, these studies primarily focus on Short Chain-of-Thought (CoT) models, the critique finetuning for long CoT models has not been further explored yet.

Report issue for preceding element

In this paper, we first propose Self-Critique Fine-Tuning (SCFT), a self-supervised framework that initializes effective reflective capabilities using only self-generated data. SCFT prompts the model to critique its own outputs, filters high-quality critiques via rejection sampling, and fine-tunes the model to internalize error correction. Building on this, we introduce Reinforcement Learning with Effective Reflection Rewards (RLERR) to further optimize the reasoning policy. Besides standard outcome-based RL, RLERR incorporates a hierarchical reward system based on effective reflection principles. Unlike sparse outcome rewards that only assess the final answer, RLERR provides dense feedback on the quality of the reflection process itself—rewarding truthfulness, constructiveness, and specificity. This guides the model to internalize the self-correction process and avoid superficial checks.

Report issue for preceding element

Our approach yields both performance improvements and behavioral gains.
SCFT consistently enhances reasoning accuracy across various model scales. Compared with DeepSeek-R1-Distill-Qwen-7B, SCFT improves accuracy by 4.8% and 6.0% on AIME2024 and AIME2025, respectively. Even against the larger DeepSeek-R1-Distill-Qwen-14B, SCFT delivers consistent improvements of 0.9% and 3.8% on AIME2024 and AIME2025, respectively. Beyond accuracy, SCFT also enhances the model’s reflective behavior, increasing the Effective Reflection Ratio (ERR) by more than 10% on average. Furthermore, RLERR pushes the boundary of effective reflection, enabling the DeepScaleR-1.5B-Preview model to achieve a Pass@1 of 44.2% alongside a high Effective Reflection Ratio (ERR) of 0.48. Our analysis also reveals two critical insights: (1) SCFT serves as a superior initialization for reinforcement learning compared to standard self-distillation, unlocking higher performance ceilings; and (2) the synergy between reflection-quality rewards and outcome-based rewards is essential for guiding models to internalize genuine self-correction capabilities rather than superficial critiques.

Report issue for preceding element

## 2 Related Work

Report issue for preceding element

### 2.1 Reasoning Behaviors of LRMs

Report issue for preceding element

In recent years, Large Reasoning Models (LRMs) such as DeepSeek-R1 DeepSeek-AI et al. ( [2025](https://arxiv.org/html/2601.12720v1#bib.bib3 "DeepSeek-r1: incentivizing reasoning capability in llms via reinforcement learning")) and OpenAI o1 OpenAI et al. ( [2024](https://arxiv.org/html/2601.12720v1#bib.bib10 "OpenAI o1 system card")) have achieved superior performance in complex reasoning tasks. Through large-scale reinforcement learning, these reasoning models have learned longer Chain-of-Thought (CoT) thinking Cui et al. ( [2025](https://arxiv.org/html/2601.12720v1#bib.bib11 "Process reinforcement through implicit rewards")); Team et al. ( [2025](https://arxiv.org/html/2601.12720v1#bib.bib6 "Kimi k1.5: scaling reinforcement learning with llms")); Zeng et al. ( [2025](https://arxiv.org/html/2601.12720v1#bib.bib32 "SimpleRL-zoo: investigating and taming zero reinforcement learning for open base models in the wild")); Luo et al. ( [2025](https://arxiv.org/html/2601.12720v1#bib.bib12 "DeepScaleR: surpassing o1-preview with a 1.5b model by scaling rl")) and induce sophisticated reasoning behaviors such as reflection Liu et al. ( [2025](https://arxiv.org/html/2601.12720v1#bib.bib1 "There may not be aha moment in r1-zero-like training — a pilot study")); Gandhi et al. ( [2025](https://arxiv.org/html/2601.12720v1#bib.bib13 "Cognitive behaviors that enable self-improving reasoners, or, four habits of highly effective stars")). These reasoning behaviors of LRMs have attracted widespread attention from the research community. Gandhi et al. ( [2025](https://arxiv.org/html/2601.12720v1#bib.bib13 "Cognitive behaviors that enable self-improving reasoners, or, four habits of highly effective stars")) point out that LRMs primarily improve their performance during reasoning by employing reflective behaviors like verification and backtracking. ThinkPatterns Wen et al. ( [2025b](https://arxiv.org/html/2601.12720v1#bib.bib27 "ThinkPatterns-21k: a systematic study on the impact of thinking patterns in llms")) investigates the impact of five thinking patterns, including self-critique, on the performance of LRMs. The self-critic pattern demonstrates good stability and scalability due to its two-stage generation and evaluation mechanism, offering a new perspective for enhancing the reasoning capabilities of LRMs. However, despite these reflective behaviors can enhance the reasoning ability of LRMs, Liu et al. ( [2025](https://arxiv.org/html/2601.12720v1#bib.bib1 "There may not be aha moment in r1-zero-like training — a pilot study")) note that these models do not always engage in effective reflection, they often lack substantive correction or improvement of errors during the reflection process, which limits their ability to effectively enhance answer quality. Therefore, guiding LRMs to perform effective reflection has become an important direction for current research.

Report issue for preceding element

### 2.2 Critique Learning

Report issue for preceding element

Recent advances in critique learning have significantly enhanced the ability of LLMs to evaluate and improve model outputs.
MultiCritique Lan et al. ( [2024](https://arxiv.org/html/2601.12720v1#bib.bib14 "Training language models to critique with multi-agent feedback")) leverages multi-agent feedback to generate high-quality critique data and employs reinforcement learning to further refine the model‘s critique capabilities.
AutoMathCritique Xie et al. ( [2025](https://arxiv.org/html/2601.12720v1#bib.bib15 "Teaching language models to critique via reinforcement learning")) focuses on automating the generation of step-level feedback for mathematical reasoning, significantly improving the model‘s step-by-step critique performance on complex math problems through fine-tuning.
CTRL Xi et al. ( [2024](https://arxiv.org/html/2601.12720v1#bib.bib16 "Enhancing llm reasoning via critique models with test-time and training-time supervision")) teaches language models to critique via reinforcement learning, enabling them to dynamically adjust their critique strategies based on rewards.
CFT Wang et al. ( [2025](https://arxiv.org/html/2601.12720v1#bib.bib17 "Critique fine-tuning: learning to critique is more effective than learning to imitate")) demonstrates that learning to critique is more effective than mere imitation, with models fine-tuned for critique tasks showing superior performance in generating high-quality and consistent outputs.
Nevertheless, these methods highly depend on stronger models or human experts for distillation or require a significant amount of time for reinforcement learning. Besides, previous work has not studied the effectiveness of critique fine-tuning on slow thinking models. Unlike them, SCFT focuses on the slow thinking reasoning models and constructs high-quality data through self-critique and rejection sampling to perform self-critique fine-tuning, enhancing both the model‘s generation and critique capabilities simultaneously.

Report issue for preceding element

### 2.3 Reinforcement Learning for Reasoning

Report issue for preceding element

Reinforcement learning (RL) has become a cornerstone for aligning LLMs with complex reasoning tasks DeepSeek-AI et al. ( [2025](https://arxiv.org/html/2601.12720v1#bib.bib3 "DeepSeek-r1: incentivizing reasoning capability in llms via reinforcement learning")); OpenAI et al. ( [2024](https://arxiv.org/html/2601.12720v1#bib.bib10 "OpenAI o1 system card")). Early approaches primarily utilize Outcome Reward Models (ORMs), which provide sparse feedback based solely on the correctness of the answer Cobbe et al. ( [2021](https://arxiv.org/html/2601.12720v1#bib.bib9 "Training verifiers to solve math word problems")). While effective, ORMs often struggle with credit assignment in long reasoning chains. To address this, Process Reward Models (PRMs) were introduced to provide dense feedback by evaluating intermediate reasoning steps Lightman et al. ( [2023](https://arxiv.org/html/2601.12720v1#bib.bib7 "Let’s verify step by step")); Wang et al. ( [2024b](https://arxiv.org/html/2601.12720v1#bib.bib8 "Math-shepherd: verify and reinforce llms step-by-step without human annotations")); Cui et al. ( [2025](https://arxiv.org/html/2601.12720v1#bib.bib11 "Process reinforcement through implicit rewards")). PRMs have shown significant improvements in mathematical reasoning by guiding models step-by-step. However, training PRMs typically requires expensive human annotations or supervision from super-sized models, limiting their scalability. Unlike standard PRMs that focus on step-level correctness, RLERR introduces a novel reward formulation centered on reflection quality. Instead of relying on external step-wise labels, we construct a hierarchical reward system based on effective reflection principles. This allows the model to internalize self-correction capabilities through reinforcement learning.

Report issue for preceding element

## 3 Methodology

Report issue for preceding element![Refer to caption](https://arxiv.org/html/2601.12720v1/x2.png)Figure 2: The overall pipeline of our proposed SCFT and RLERR method.Report issue for preceding element

In this section, we present a systematic framework for enhancing the reflective capabilities of Large Reasoning Models (LRMs). Our methodology consists of three main components. First, in Sec. [3.1](https://arxiv.org/html/2601.12720v1#S3.SS1 "3.1 Effective Reflection ‣ 3 Methodology ‣ Teaching Large Reasoning Models Effective Reflection"), we define the concept of Effective Reflection and its quantitative metric.
Then, as illustrated in Figure [2](https://arxiv.org/html/2601.12720v1#S3.F2 "Figure 2 ‣ 3 Methodology ‣ Teaching Large Reasoning Models Effective Reflection"), we first propose Self-Critique Fine-Tuning (SCFT) (Sec. [3.2](https://arxiv.org/html/2601.12720v1#S3.SS2 "3.2 Self-Critique Fine-Tuning (SCFT) ‣ 3 Methodology ‣ Teaching Large Reasoning Models Effective Reflection")) and then introduce Reinforcement Learning with Effective Reflection Rewards (RLERR) (Sec. [3.3](https://arxiv.org/html/2601.12720v1#S3.SS3 "3.3 Reinforcement Learning with Effective Reflection Rewards (RLERR) ‣ 3 Methodology ‣ Teaching Large Reasoning Models Effective Reflection")). SCFT is a supervised learning approach that leverages high-quality self-generated critiques to equip the model with fundamental reflective skills. RLERR incentivizes the model to generate deep reflections that effectively correct errors, optimizing the model’s policy using the defined reward signals.

Report issue for preceding element

### 3.1 Effective Reflection

Report issue for preceding element

Effective reflection is the process by which a large reasoning model identifies and corrects errors in its reasoning or confirms that the reasoning is correct, leading to improved solutions.
Let xx represent a question and yy represent a model’s response. We consider a reflection r⊂yr\\subset y to be effective if it contributes to arriving at a correct solution.

Report issue for preceding element

Previous workLiu et al. ( [2025](https://arxiv.org/html/2601.12720v1#bib.bib1 "There may not be aha moment in r1-zero-like training — a pilot study")) uses the number of reflection keywords to generally reveal that the reflection of LRMs is not always effective. These reflections might introduce errors into originally correct answers or fail to produce a valid answer after several reflections. In order to see more clearly the proportion of effective reflection in the model reasoning process and measure reflection effectiveness, we introduce the Effective Reflection Ratio (ERR), defined as the proportion of reflections that contribute to correct solutions:

Report issue for preceding element

|     |     |     |     |
| --- | --- | --- | --- |
|  | ERR=∑i=1nAccuracy​(yi)⋅R​(yi)∑i=1nR​(yi)\\text{ERR}=\\frac{\\sum\_{i=1}^{n}\\text{Accuracy}(y\_{i})\\cdot R(y\_{i})}{\\sum\_{i=1}^{n}R(y\_{i})} |  | (1) |

where nn is the total number of responses, yiy\_{i} denotes the ii-th response, R​(yi)R(y\_{i}) counts the number of reflections in response yiy\_{i}, and Accuracy​(yi)∈{0,1}\\text{Accuracy}(y\_{i})\\in\\{0,1\\} is a binary indicator of whether yiy\_{i} is fully correct.

Report issue for preceding element

### 3.2 Self-Critique Fine-Tuning (SCFT)

Report issue for preceding element

Self-Critique Fine-Tuning (SCFT) aims to teach large reasoning models to effectively reflect. In this subsection, we present the construction of training data using self-critique (Sec. [3.2.1](https://arxiv.org/html/2601.12720v1#S3.SS2.SSS1 "3.2.1 Construction of Training Data ‣ 3.2 Self-Critique Fine-Tuning (SCFT) ‣ 3 Methodology ‣ Teaching Large Reasoning Models Effective Reflection")), training objective, and inference mode (Sec. [3.2.2](https://arxiv.org/html/2601.12720v1#S3.SS2.SSS2 "3.2.2 Training Objective ‣ 3.2 Self-Critique Fine-Tuning (SCFT) ‣ 3 Methodology ‣ Teaching Large Reasoning Models Effective Reflection")).

Report issue for preceding element

#### 3.2.1 Construction of Training Data

Report issue for preceding element

Given a question qq, the model ℳ\\mathcal{M} first generates a response yy, followed by a critique cc that evaluates the correctness of yy:

Report issue for preceding element

|     |     |     |     |
| --- | --- | --- | --- |
|  | y=ℳ​(q),c=ℳ​(t​‖q‖​y)y=\\mathcal{M}\\left(q\\right),c=\\mathcal{M}\\left(t{\\\|q\\\|}y\\right) |  | (2) |

where tt denotes a predefined critique prompt template, and ∥\\\| represents sequence concatenation. We then employ ground truth based rejection sampling to filter high-quality data as in previous work Face ( [2025](https://arxiv.org/html/2601.12720v1#bib.bib18 "Open r1: a fully open reproduction of deepseek-r1")); Team ( [2025](https://arxiv.org/html/2601.12720v1#bib.bib19 "Open Thoughts")). A generated triplet (q,y,c)(q,y,c) is included in the training set if and only if it satisfies the following correctness filter:

Report issue for preceding element

|     |     |     |     |
| --- | --- | --- | --- |
|  | ℱ​(q,y,c)={1,if Acc​(y)=1​ and Acc​(c)=1,1,if Acc​(y)=0​ and Acc​(c)=1,0,otherwise,\\mathcal{F}(q,y,c)=\\begin{cases}1,&\\text{if }\\text{Acc}(y)=1\\text{ and }\\text{Acc}(c)=1,\\\<br>1,&\\text{if }\\text{Acc}(y)=0\\text{ and }\\text{Acc}(c)=1,\\\<br>0,&\\text{otherwise},\\end{cases} |  | (3) |

where Acc​(⋅)\\text{Acc}(\\cdot) evaluates correctness against the ground truth. This filtering ensures that only samples with valid self-reflection behavior are retained. The full training dataset is then defined as:

Report issue for preceding element

|     |     |     |     |
| --- | --- | --- | --- |
|  | 𝒟={(qi,yi,ci)∣ℱ​(qi,yi,ci)=1}.\\mathcal{D}=\\left\\{(q\_{i},y\_{i},c\_{i})\\mid\\mathcal{F}(q\_{i},y\_{i},c\_{i})=1\\right\\}. |  | (4) |

Importantly, all responses and critiques are self-generated by the same model ℳ\\mathcal{M}, without reliance on external supervision or stronger teacher models. Both outputs adopt a long-form Chain-of-Thought (CoT) format, consisting of an explicit reasoning trace enclosed by "<think>" and "</think>" tags, followed by a concise answer summary. Examples of accepted training instances are shown in Appendix [A.2](https://arxiv.org/html/2601.12720v1#A1.SS2 "A.2 Example of Training Data ‣ Appendix A Appendix ‣ Teaching Large Reasoning Models Effective Reflection").

Report issue for preceding element

#### 3.2.2 Training Objective

Report issue for preceding element

During the fine-tuning phase, we train the model on the constructed dataset DD, where the input is “Please critique whether the following solution to the question is correct. Question: {qq} Solution: {yy}”, and the expected output is the critique cc. The training objective is to minimize the negative log-likelihood:

Report issue for preceding element

|     |     |     |     |
| --- | --- | --- | --- |
|  | ℒ=−∑(q,y,c)∈Dlog⁡P​(c\|q,y;θ)\\mathcal{L}=-\\sum\_{(q,y,c)\\in D}\\log P(c\|q,y;\\theta) |  | (5) |

where θ\\theta represents the model parameters, qq is the question, yy is the response, and cc is the critique.

Report issue for preceding element

At inference time, we can regard the trained model as both a generative model (producing answers) and a critique model (evaluating and improving answers) simultaneously by simply modifying the prompt. For the generative mode, we input the question qq and obtain the response yy. For the critique mode, we input the question qq along with the generated response yy to produce the critique cc. In particular, we did not use additional question-answer pairs to train the model.

Report issue for preceding element

After training, the model can act as a generative model or a critique model by modifying the prompt. While SCFT equips the model with preliminary reflective capabilities, to further enhance the accuracy and robustness of reflection, we utilize the SCFT-tuned model as the initialization for the subsequent reinforcement learning stage.

Report issue for preceding element

### 3.3 Reinforcement Learning with Effective Reflection Rewards (RLERR)

Report issue for preceding element

While SCFT provides a strong initialization for reflective reasoning, supervised fine-tuning alone is limited by the quality of static data. To further align the model with Effective Reflection, we introduce RLERR, which is reinforcement learning with a hierarchical reward system based on five core principles of reflection.

Report issue for preceding element

#### 3.3.1 Hierarchical Reflection Principles

Report issue for preceding element

We define five principles (P1P\_{1} to P5P\_{5}) for evaluating reflection quality, ranked from fundamental validity to advanced reasoning optimization. Lower-level principles act as prerequisites for higher-level rewards.

Report issue for preceding element

- •


P1P\_{1}: Truthfulness (Critical Necessity). The reflection must objectively judge the correctness of the previous step. It should not hallucinate errors in correct steps nor blindly validate incorrect ones.

Report issue for preceding element

- •


P2P\_{2}: Constructiveness (Problem Solving). The reflection must not only identify an error but also propose a valid correction or a specific next step. Mere complaints (e.g., “This is wrong”) without guidance are penalized.

Report issue for preceding element

- •


P3P\_{3}: Specificity (Precision). The critique must pinpoint the exact location or logic of the error (e.g., “calculation error in step 2” vs. “the answer looks wrong”).

Report issue for preceding element

- •


P4P\_{4}: Substantiveness (Depth). The reflection should involve rigorous verification (e.g., re-deriving a formula or checking constraints) rather than superficial checks.

Report issue for preceding element

- •


P5P\_{5}: InfoGain (Efficiency). The reflection should break repetitive loops or open new reasoning paths that significantly reduce uncertainty, avoiding redundant restatements.

Report issue for preceding element


#### 3.3.2 Training Setup

Report issue for preceding element

We employ GRPO as our RL algorithm and use the SCFT-initialized model as the policy model πθ\\pi\_{\\theta}.
To obtain dense and scalable reward signals, we utilize a strong LLM (e.g., GPT-4o) as the Reward Model. The Reward Model evaluates the generated trajectory based on the five principles defined above and assigns a holistic scalar score R∈\[0,10\]R\\in\[0,10\].
The scoring process is guided by a comprehensive prompt (detailed in Appendix [A.1](https://arxiv.org/html/2601.12720v1#A1.SS1 "A.1 Reflection Evaluation Prompt ‣ Appendix A Appendix ‣ Teaching Large Reasoning Models Effective Reflection")) that instructs the judge to heavily penalize hallucinations (violating P1P\_{1}) while rewarding constructive and specific insights (P2P\_{2}-P5P\_{5}). This approach allows the optimization process to capture the nuance of effective reflection without rigid rule-based filtering. We employ GRPO to maximize the expected reward:

Report issue for preceding element

|     |     |     |     |
| --- | --- | --- | --- |
|  | maxθ⁡𝔼(q)∼D,y∼πθ​\[R​(q,y)\]\\max\_{\\theta}\\mathbb{E}\_{(q)\\sim D,y\\sim\\pi\_{\\theta}}\[R(q,y)\] |  | (6) |

where R​(q,y)R(q,y) is the score provided by the LLM judge.

Report issue for preceding element

## 4 Experimental Methodology

Report issue for preceding element

In this section, we describe the datasets, evaluation metrics, baselines, and implementation details.

Report issue for preceding element

Dataset. For the SCFT training set, we use the mathematical problems provided in DeepScaleRLuo et al. ( [2025](https://arxiv.org/html/2601.12720v1#bib.bib12 "DeepScaleR: surpassing o1-preview with a 1.5b model by scaling rl")) to construct the data through self-critique. For the RL training set, we usethe DAPO-Math-17K dataset (Yu et al., [2025](https://arxiv.org/html/2601.12720v1#bib.bib2 "DAPO: an open-source llm reinforcement learning system at scale")), which is a curated collection of approximately 17,000 competition-level math problems. For testing, we evaluate the effectiveness of Self-Critique Fine-Tuning on AIME2024 Beeching et al. ( [2024](https://arxiv.org/html/2601.12720v1#bib.bib20 "NuminaMath 7b tir")), AIME2025 Ye et al. ( [2025](https://arxiv.org/html/2601.12720v1#bib.bib21 "LIMO: less is more for reasoning")), MATH-500 Hendrycks et al. ( [2021](https://arxiv.org/html/2601.12720v1#bib.bib22 "Measuring mathematical problem solving with the math dataset")), and GPQA datasets Rein et al. ( [2023](https://arxiv.org/html/2601.12720v1#bib.bib23 "GPQA: a graduate-level google-proof qa benchmark")).

Report issue for preceding element

Evaluation Metrics. We follow previous work Chen et al. ( [2021](https://arxiv.org/html/2601.12720v1#bib.bib24 "Evaluating large language models trained on code")); Li et al. ( [2024](https://arxiv.org/html/2601.12720v1#bib.bib28 "Mmcode: evaluating multi-modal code large language models with visually rich programming problems")); Wang et al. ( [2024a](https://arxiv.org/html/2601.12720v1#bib.bib29 "INTERVENOR: prompting the coding ability of large language models with the interactive chain of repair")); Yang et al. ( [2024b](https://arxiv.org/html/2601.12720v1#bib.bib30 "Enhancing the code debugging ability of llms via communicative agent based data refinement")); Luo et al. ( [2023](https://arxiv.org/html/2601.12720v1#bib.bib31 "Wizardcoder: empowering code large language models with evol-instruct")) and we use Pass@kChen et al. ( [2021](https://arxiv.org/html/2601.12720v1#bib.bib24 "Evaluating large language models trained on code")) to evaluate the effectiveness of different models. Pass@k represents the probability that at least one correct solution appears among the top kk generated solutions for each problem:

Report issue for preceding element

|     |     |     |     |
| --- | --- | --- | --- |
|  | Pass@​k:=𝔼Problems​\[1−(n−ck)(nk)\]\\text{Pass@}k:=\\underset{\\text{Problems}}{\\operatorname\*{\\mathbb{E}}}\\left\[1-\\frac{\\binom{n-c}{k}}{\\binom{n}{k}}\\right\] |  | (7) |

where nn denotes the total number of generated solutions, cc is the number of correct solutions, and kk is the number of top-ranked solutions being evaluated. In this work, we set k=1k=1.
The Pass@1 accuracy is averaged over 16 samples per problem.
Besides, we use ERR to evaluate the proportion of effective reflection in the response.

Report issue for preceding element

| Model | AIME2024 | AIME2025 | MATH-500 | GPQA Diamond | Avg. Pass@1 | Avg. ERR |
| Pass@1 | ERR | Pass@1 | ERR | Pass@1 | ERR | Pass@1 | ERR |
| Qwen-2.5-7B-SimpleRL-Zoo | 15.0 | 0.06 | 5.2 | 0.03 | 69.1 | 0.26 | 31.3 | 0.14 | 30.1 | 0.12 |
| Light-R1-7B-DS | 57.7 | 0.32 | 46.4 | 0.23 | 91.1 | 0.75 | 47.2 | 0.44 | 60.6 | 0.44 |
| AReaL-boba-RL-7B | 62.7 | 0.39 | 49.4 | 0.24 | 93.8 | 0.71 | 48.0 | 0.45 | 63.5 | 0.45 |
| LIMO-32B | 55.2 | 0.24 | 44.8 | 0.19 | 94.8 | 0.77 | 63.1 | 0.50 | 64.5 | 0.43 |
| s1-32B | 50.2 | 0.22 | 26.0 | 0.15 | 92.6 | 0.67 | 57.0 | 0.47 | 56.5 | 0.38 |
| DeepSeek-R1-Distill-Qwen-1.5B | 29.0 | 0.13 | 23.3 | 0.14 | 82.6 | 0.46 | 33.3 | 0.34 | 42.0 | 0.27 |
| \+ Self-Distill | 32.3 | 0.15 | 21.9 | 0.06 | 81.4 | 0.50 | 31.1 | 0.30 | 41.7 | 0.25 |
| \+ SCFT | 31.9 | 0.15 | 22.9 | 0.13 | 82.6 | 0.53 | 32.7 | 0.33 | 42.5 | 0.29 |
| DeepScaleR-1.5B-Preview | 40.2 | 0.32 | 28.5 | 0.17 | 87.7 | 0.77 | 32.3 | 0.41 | 47.2 | 0.42 |
| \+ Self-Distill | 37.3 | 0.43 | 29.8 | 0.19 | 87.2 | 0.70 | 30.2 | 0.41 | 46.1 | 0.43 |
| \+ SCFT | 41.3 | 0.40 | 28.3 | 0.19 | 87.3 | 0.71 | 32.3 | 0.43 | 47.3 | 0.43 |
| \+ RLERR | 44.2 | 0.48 | 31.0 | 0.33 | 89.5 | 0.76 | 37.9 | 0.50 | 50.7 | 0.52 |
| DeepSeek-R1-Distill-Qwen-7B | 55.6 | 0.26 | 39.4 | 0.14 | 91.9 | 0.65 | 47.1 | 0.46 | 58.5 | 0.38 |
| \+ Self-Distill | 57.9 | 0.25 | 40.2 | 0.19 | 89.8 | 0.63 | 48.5 | 0.42 | 59.1 | 0.37 |
| \+ SCFT | 60.2 | 0.38 | 45.4 | 0.21 | 92.4 | 0.72 | 48.7 | 0.40 | 61.7 | 0.43 |
| \+ RLERR | 63.1 | 0.50 | 48.1 | 0.33 | 92.2 | 0.80 | 57.0 | 0.51 | 65.1 | 0.54 |
| DeepSeek-R1-Distill-Qwen-14B | 70.4 | 0.52 | 50.0 | 0.27 | 92.4 | 0.68 | 59.5 | 0.58 | 68.1 | 0.51 |
| \+ Self-Distill | 70.4 | 0.52 | 52.1 | 0.35 | 92.4 | 0.73 | 59.5 | 0.53 | 68.6 | 0.53 |
| \+ SCFT | 71.3 | 0.53 | 53.8 | 0.47 | 93.4 | 0.77 | 60.8 | 0.53 | 69.8 | 0.57 |

Table 1: Overall Performance of Self-Critique Fine-Tuning. The Pass@1 is averaged over 16 samples per problem. Due to the limitations of computing resources, we only conduct RLERR on DeepScaleR-1.5B-Preview and DeepSeek-R1-Distill-Qwen-7B.Report issue for preceding element

Baselines. In our experiments, we perform self-critique fine-tuning on DeepSeek-R1-Distill-Qwen-1.5B/7B/14BDeepSeek-AI et al. ( [2025](https://arxiv.org/html/2601.12720v1#bib.bib3 "DeepSeek-r1: incentivizing reasoning capability in llms via reinforcement learning")) and DeepScaleR-1.5B-Preview Luo et al. ( [2025](https://arxiv.org/html/2601.12720v1#bib.bib12 "DeepScaleR: surpassing o1-preview with a 1.5b model by scaling rl")), and compare it with the self-distillation method. The data for self-distillation is generated by the model itself and filtered using ground truth to obtain high-quality data. The amount of self-distill data is the same as that of SCFT data. Furthermore, we also make comparisons with some advanced models, such as Qwen-2.5-7B-SimpleRL-ZooZeng et al. ( [2025](https://arxiv.org/html/2601.12720v1#bib.bib32 "SimpleRL-zoo: investigating and taming zero reinforcement learning for open base models in the wild")), Light-R1-7B-DSWen et al. ( [2025a](https://arxiv.org/html/2601.12720v1#bib.bib33 "Light-r1: curriculum sft, dpo and rl for long cot from scratch and beyond")), AReaL-boba-RL-7BRL Lab ( [2025](https://arxiv.org/html/2601.12720v1#bib.bib34 "AReaL: ant reasoning rl")), LIMO-32BYe et al. ( [2025](https://arxiv.org/html/2601.12720v1#bib.bib21 "LIMO: less is more for reasoning")), and s1-32BMuennighoff et al. ( [2025](https://arxiv.org/html/2601.12720v1#bib.bib5 "S1: simple test-time scaling")).

Report issue for preceding element

Implementation Details. During SCFT stage, all models are trained using the Llama-Factory framework Zheng et al. ( [2024](https://arxiv.org/html/2601.12720v1#bib.bib25 "LlamaFactory: unified efficient fine-tuning of 100+ language models")). We set the learning rate to 1e-5, the number of training epochs to 10, and the batch size to 64.
During RL, we use GRPO as the RL algorithm. For hyperparameters, we set the batch size and mini-batch size to 6464, and for each problem, we rollout 88 responses. The maximum lengths for prompts and responses are 1,0241,024 and 16,38416,384 tokens, respectively. The learning rate is set to 1​e−61e-6, and we adopt the AdamW optimizer for the policy model. During inference, we set the temperature to 0.6 and the maximum generation length to 32,768 tokens.

Report issue for preceding element

## 5 Evaluation Results

Report issue for preceding element

In this section, we evaluate the overall performance of Self-Critique Fine-Tuning (SCFT) and RLERR. Then we conduct ablation studies and also explore the influence of using different critique models on the performance of SCFT. Finally, we demonstrate that SCFT serves as a superior initialization for RL and RLERR (combining outcome and effective reflection rewards) significantly outperforms using outcome or reflection rewards in isolation.

Report issue for preceding element

### 5.1 Overall Performance

Report issue for preceding element![Refer to caption](https://arxiv.org/html/2601.12720v1/x3.png)Figure 3: The impact of the amount of SCFT and Self-Distill training data on the model performance. The base model is DeepSeek-R1-Distill-Qwen-1.5B. The Pass@1 represents the average performance across all test sets.Report issue for preceding element

The overall performance of SCFT and RLERR is shown in Table [1](https://arxiv.org/html/2601.12720v1#S4.T1 "Table 1 ‣ 4 Experimental Methodology ‣ Teaching Large Reasoning Models Effective Reflection"). SCFT consistently improves reasoning performance across models of varying scales. The 7B and 14B variants of DeepSeek-R1-Distill-Qwen achieve the most significant gains: SCFT boosts average Pass@1 by 2.6% (58.5→61.7) and 1.7% (68.1→69.8), respectively, outperforming self-distillation baselines. Additionally, the effective reflection ratios of the 7B and 14B models increase by 5% and 6%, respectively, indicating that the models achieve more accurate reflection through SCFT. Notably, on the more challenging datasets AIME2024 and AIME2025, the 7B model’s Pass@1 improves by 4.6% and 6%, respectively, demonstrating that SCFT can further enhance the model’s reasoning capabilities. Moreover, on the 1.5B model, SCFT achieves marginal gains on Pass@1. For DeepScaleR-1.5B-Preview, SCFT brings a 4.3% improvement in Pass@16 (Figure [5](https://arxiv.org/html/2601.12720v1#A1.F5 "Figure 5 ‣ A.3 Additional Performance Analysis ‣ Appendix A Appendix ‣ Teaching Large Reasoning Models Effective Reflection")), suggesting that SCFT can raise the upper limit of the model’s performance. Additionally, the 7B models after SCFT achieve comparable results with the advanced 7B models SimpleRL-Zoo, Light-R1-7B-DS, and AReaL-boba-RL-7B, which have undergone extensive reinforcement learning. Moreover, it outperforms the larger-scale s1-32B model and achieves comparable results with LIMO-32B.

Report issue for preceding element

RLERR yields further improvements upon SCFT, significantly enhancing both reasoning accuracy and reflection quality. As shown in Table [1](https://arxiv.org/html/2601.12720v1#S4.T1 "Table 1 ‣ 4 Experimental Methodology ‣ Teaching Large Reasoning Models Effective Reflection"), applying RLERR to DeepScaleR-1.5B-Preview results in an average Pass@1 of 50.7% and an average ERR of 0.52, surpassing the SCFT stage by 3.4% and 0.09, respectively. Similarly, for DeepSeek-R1-Distill-Qwen-7B, RLERR pushes the average Pass@1 to 65.1%, demonstrating a substantial gain over the SCFT baseline (61.7%). Notably, the 7B model trained with RLERR achieves state-of-the-art performance among models of similar size, outperforming AReaL-boba-RL-7B (63.5%) and Light-R1-7B-DS (60.6%). Furthermore, it even surpasses the 32B-scale model LIMO-32B (64.5%) in average accuracy.

Report issue for preceding element

### 5.2 Ablation Studies

Report issue for preceding element

| Model | \# c->c | Pass@1 | Pass@16 | ERR |
| --- | --- | --- | --- | --- |
| DS-R1-Dis-Qwen-7B | - | 58.5 | 82.0 | 0.38 |
| --- | --- | --- | --- | --- |
|  | 0.0 | 60.8 | 84.9 | 0.38 |
|  | 0.5k | 61.7 | 86.4 | 0.43 |
|  | 1k | 60.7 | 85.0 | 0.38 |
|  | 1.5k | 60.3 | 85.0 | 0.41 |
|  | 2k | 60.8 | 86.3 | 0.40 |
|  | 2.5k | 60.2 | 84.7 | 0.37 |
| \+ SCFT (# i->c=1k) | 3k | 60.2 | 85.8 | 0.39 |

Table 2: The Trade-off Between Error Correction (i→c) and Correctness Reinforcement (c→c) in Self-Critique Fine-Tuning. # i→c denotes the number of critiques correcting incorrect responses, while # c→c represents the number of critiques validating correct responses. The experimental results represent the average performance across all test sets.Report issue for preceding element

To further investigate the effect of the proportion and amount of data used for self-Critique fine-tuning (SCFT) on the performance of fine-tuning, we perform the ablation Studies.
The data used for SCFT can be categorized into two types: i→c and c→c. Specifically, i→c represents critiques that identify the mistakes in incorrect responses and give the correct answer, while c→c represents critiques that confirm correct responses. As shown in Table [2](https://arxiv.org/html/2601.12720v1#S5.T2 "Table 2 ‣ 5.2 Ablation Studies ‣ 5 Evaluation Results ‣ Teaching Large Reasoning Models Effective Reflection"), we investigate the impact of the ratio of these two types of data on model performance. By fixing the amount of i→c data at 1k and varying the amount of c→c data, we observe that the optimal performance is achieved when the ratio of i→c to c→c is 2:1.

Report issue for preceding element

Following this optimal ratio, we further explore the influence of the total amount of critique data used for SCFT on model performance. As shown in Figure [3](https://arxiv.org/html/2601.12720v1#S5.F3 "Figure 3 ‣ 5.1 Overall Performance ‣ 5 Evaluation Results ‣ Teaching Large Reasoning Models Effective Reflection"), when scaling the training data from 1K to 6K samples, SCFT provides a greater performance improvement than self-distillation. However, as the amount of data increases, the performance gains of SCFT and self-distillation gradually level off. This indicates that excessively increasing the data for SCFT and self-distillation does not lead to a continuous improvement in model performance.

Report issue for preceding element

| Model | Pass@1 | Pass@16 | ERR |
| --- | --- | --- | --- |
| DPSK-R1-Dis-Qwen-7B | 55.6 | 83.3 | 0.26 |
| \+ WebInstruct-CFT | 44.8 | 80.0 | 0.21 |
| \+ Self-Distill FT | 57.9 | 86.7 | 0.25 |
| \+ R1-Distill FT | 59.2 | 86.7 | 0.41 |
| \+ Self-Critique FT | 60.2 | 86.7 | 0.38 |
| \+ R1-Critique FT | 60.2 | 90.0 | 0.49 |

Table 3: The Performance Comparison of Critique Fine-Tuning Using Different Critique Models on AIME 2024. FT represents Finetuning.Report issue for preceding element

| Critique Model | Accuracy@t1 | Accuracy@t2 | Δ\\Delta(t1, t2) | Δi→c\\Delta\_{i\\to c}(t1, t2) | Δc→i\\Delta\_{c\\to i}(t1, t2) |
| --- | --- | --- | --- | --- | --- |
| DPSK-R1-Dis-Qwen-7B | 23.3 | 20.0 | -3.3 | 3.3 | 6.7 |
| \+ Self-Critique FT | 23.3 | 33.3 | 10.0 | 13.3 | 3.3 |
| \+ RLERR | 23.3 | 50.0 | 26.7 | 30.0 | 3.3 |
| \+ R1-Critique FT | 23.3 | 40.0 | 16.7 | 20.0 | 3.3 |

Table 4: The Critique Performance of Critique Fine-Tuning on AIME 2024. The initial response generation model is Qwen2.5-Math-7B-Instruct. Accuracy@t1 represents the accuracy of the initial generation. Accuracy@t2 represents the accuracy of the critique model after one round of correction. Δi→c\\Delta\_{i\\to c}(t1, t2) indicates the fraction of problems that are incorrect in the first generation but become correct after critique. Δc→i\\Delta\_{c\\to i}(t1, t2) indicates the fraction of problems that are correct in the first generation but become incorrect after critique. FT represents Finetuning.Report issue for preceding element

### 5.3 Performance Comparison of CFT Using Different Critique Models

Report issue for preceding element

We investigate the impact of using a stronger model as a critique model to construct data for Critique Fint-Tuning on model performance.
The results are shown in Table [3](https://arxiv.org/html/2601.12720v1#S5.T3 "Table 3 ‣ 5.2 Ablation Studies ‣ 5 Evaluation Results ‣ Teaching Large Reasoning Models Effective Reflection"). WebInstruct-CFT is a critique-based instruction dataset derived from WebInstruct. It includes critiques of responses, and the responses and critiques are all in the form of Short Chain-of-Thought (short CoT). Self/R1-distill and Self/R1-Critique are the data for SFT and SCFT constructed by self and DeepSeek-R1, respectively. From the results, we observe that fine-tuning with data constructed by a stronger model can achieve better performance. Specifically, when using R1-Critique finetuning, both the Pass@1 and Pass@16 metrics achieve the highest scores. Furthermore, for the Long CoT model, if short CoT data (WebInstruct-CFT) is used for training, the performance will be reduced.

Report issue for preceding element

We further explore the critique ability of the model, and the results are shown in Table [4](https://arxiv.org/html/2601.12720v1#S5.T4 "Table 4 ‣ 5.2 Ablation Studies ‣ 5 Evaluation Results ‣ Teaching Large Reasoning Models Effective Reflection"). We use Qwen2.5-Math-7B-InstructYang et al. ( [2024a](https://arxiv.org/html/2601.12720v1#bib.bib36 "Qwen2.5-math technical report: toward mathematical expert model via self-improvement")) as the generative model to generate the initial response and use different models for critique. From the results, we can see that DeepSeek-R1-Distill-Qwen-7B has a poor ability to correct incorrect responses and cannot distinguish the correctness of responses, often modifying correct responses to incorrect ones. In contrast, the model‘s critique ability is significantly enhanced after SCFT and RLERR, and the model has stronger discrimination capabilities, avoiding the modification of correct responses to incorrect ones. Moreover, by using a stronger model, DeepSeek-R1, to construct SCFT data, the model‘s critique ability is further improved compared to self-critique.

Report issue for preceding element

![Refer to caption](https://arxiv.org/html/2601.12720v1/x4.png)(a) Impact of Initialization Strategies.Report issue for preceding element

![Refer to caption](https://arxiv.org/html/2601.12720v1/x5.png)(b) Ablation on Reward Signals.Report issue for preceding element

Figure 4: Analysis of DeepScaleR-1.5B-Preview RL Dynamics on AIME2024. (a) The SCFT-initialized model (green) achieves a higher performance ceiling. (b) RLERR (combining outcome and effective reflection rewards) significantly outperforms using outcome or reflection rewards in isolation.Report issue for preceding element

### 5.4 SCFT Facilitates More Effective RL

Report issue for preceding element

In this subsection, we investigate the training dynamics of Reinforcement Learning with Effective Reflection Rewards (RLERR) under different settings using DeepScaleR-1.5B-Preview.

Report issue for preceding element

Impact of Initialization.
As shown in Figure [4(a)](https://arxiv.org/html/2601.12720v1#S5.F4.sf1 "In Figure 4 ‣ 5.3 Performance Comparison of CFT Using Different Critique Models ‣ 5 Evaluation Results ‣ Teaching Large Reasoning Models Effective Reflection"), the SCFT-initialized model (green) consistently achieves a higher performance ceiling compared to the Base and Self-Distill baselines, frequently surpassing 47% Pass@1. This demonstrates that SCFT provides a superior structural prior for self-correction, enabling the model to avoid local optima and explore the solution space more effectively than models that merely mimic correct answers.

Report issue for preceding element

Ablation on Reward Signals.
Figure [4(b)](https://arxiv.org/html/2601.12720v1#S5.F4.sf2 "In Figure 4 ‣ 5.3 Performance Comparison of CFT Using Different Critique Models ‣ 5 Evaluation Results ‣ Teaching Large Reasoning Models Effective Reflection") illustrates the necessity of our hierarchical reward system. While models using only outcome or reflection rewards stagnate around 42-44% accuracy, the combined RLERR approach (green) achieves a significant boost, peaking near 49%. This confirms that the synergy between process-oriented reflection rewards and result-oriented outcome rewards is crucial for unlocking the full reasoning potential of LRMs.

Report issue for preceding element

## 6 Conclusion

Report issue for preceding element

We introduce SCFT and RLERR, a two-stage method designed to transform superficial self-reflections in Large Reasoning Models into effective error-correction mechanisms. By leveraging self-generated critiques via rejection sampling and optimizing with hierarchical reflection rewards, our approach significantly improves both reasoning accuracy and the quality of self-correction. Experiments demonstrate that our method outperforms state-of-the-art baselines, enabling models to autonomously identify and rectify errors without relying on expensive external annotations.

Report issue for preceding element

## Limitations

Report issue for preceding element

Our experiments demonstrate that smaller models (e.g., 1.5B parameters) exhibit limited gains from SCFT. This suggests that models with fewer parameters may lack the capacity to effectively leverage self-critique signals to enhance their reasoning capabilities. Moreover, the rejection sampling process depends on access to ground-truth answers, limiting its applicability in domains where labeled data is scarce. Finally, while we mitigate superficial reflection, there is a risk that the model becomes overly cautious, occasionally attempting to correct already valid reasoning steps.

Report issue for preceding element

## Ethics Statement

Report issue for preceding element

This work utilizes publicly available datasets (e.g., AIME, MATH-500) that contain no personally identifiable information or offensive content. Our training objective is grounded in objective mathematical correctness, minimizing the risk of hallucinating harmful content. We acknowledge the environmental impact of computational training costs and commit to releasing our code and models to facilitate reproducibility and reduce redundant efforts.

Report issue for preceding element

## References

Report issue for preceding element

- E. Beeching, S. C. Huang, A. Jiang, J. Li, B. Lipkin, Z. Qina, K. Rasul, Z. Shen, R. Soletskyi, and L. Tunstall (2024)↑NuminaMath 7b tir.
Numina Hugging Face.
Note: [https://huggingface.co/AI-MO/NuminaMath-7B-TIR](https://huggingface.co/AI-MO/NuminaMath-7B-TIR "")Cited by: [§4](https://arxiv.org/html/2601.12720v1#S4.p2.1 "4 Experimental Methodology ‣ Teaching Large Reasoning Models Effective Reflection").

- M. Chen, J. Tworek, H. Jun, Q. Yuan, H. P. de Oliveira Pinto, J. Kaplan, H. Edwards, Y. Burda, N. Joseph, G. Brockman, A. Ray, R. Puri, G. Krueger, M. Petrov, H. Khlaaf, G. Sastry, P. Mishkin, B. Chan, S. Gray, N. Ryder, M. Pavlov, A. Power, L. Kaiser, M. Bavarian, C. Winter, P. Tillet, F. P. Such, D. Cummings, M. Plappert, F. Chantzis, E. Barnes, A. Herbert-Voss, W. H. Guss, A. Nichol, A. Paino, N. Tezak, J. Tang, I. Babuschkin, S. Balaji, S. Jain, W. Saunders, C. Hesse, A. N. Carr, J. Leike, J. Achiam, V. Misra, E. Morikawa, A. Radford, M. Knight, M. Brundage, M. Murati, K. Mayer, P. Welinder, B. McGrew, D. Amodei, S. McCandlish, I. Sutskever, and W. Zaremba (2021)↑Evaluating large language models trained on code.
External Links: 2107.03374,
[Link](https://arxiv.org/abs/2107.03374 "")Cited by: [§4](https://arxiv.org/html/2601.12720v1#S4.p3.1 "4 Experimental Methodology ‣ Teaching Large Reasoning Models Effective Reflection").

- K. Cobbe, V. Kosaraju, M. Bavarian, M. Chen, H. Jun, L. Kaiser, M. Plappert, J. Tworek, J. Hilton, R. Nakano, C. Hesse, and J. Schulman (2021)↑Training verifiers to solve math word problems.
External Links: 2110.14168,
[Link](https://arxiv.org/abs/2110.14168 "")Cited by: [§2.3](https://arxiv.org/html/2601.12720v1#S2.SS3.p1.1 "2.3 Reinforcement Learning for Reasoning ‣ 2 Related Work ‣ Teaching Large Reasoning Models Effective Reflection").

- G. Cui, L. Yuan, Z. Wang, H. Wang, W. Li, B. He, Y. Fan, T. Yu, Q. Xu, W. Chen, J. Yuan, H. Chen, K. Zhang, X. Lv, S. Wang, Y. Yao, X. Han, H. Peng, Y. Cheng, Z. Liu, M. Sun, B. Zhou, and N. Ding (2025)↑Process reinforcement through implicit rewards.
External Links: 2502.01456,
[Link](https://arxiv.org/abs/2502.01456 "")Cited by: [§1](https://arxiv.org/html/2601.12720v1#S1.p1.1 "1 Introduction ‣ Teaching Large Reasoning Models Effective Reflection"),
[§2.1](https://arxiv.org/html/2601.12720v1#S2.SS1.p1.1 "2.1 Reasoning Behaviors of LRMs ‣ 2 Related Work ‣ Teaching Large Reasoning Models Effective Reflection"),
[§2.3](https://arxiv.org/html/2601.12720v1#S2.SS3.p1.1 "2.3 Reinforcement Learning for Reasoning ‣ 2 Related Work ‣ Teaching Large Reasoning Models Effective Reflection").

- DeepSeek-AI, D. Guo, D. Yang, H. Zhang, J. Song, R. Zhang, R. Xu, Q. Zhu, S. Ma, P. Wang, X. Bi, X. Zhang, X. Yu, Y. Wu, Z. F. Wu, Z. Gou, Z. Shao, Z. Li, Z. Gao, A. Liu, B. Xue, B. Wang, B. Wu, B. Feng, C. Lu, C. Zhao, C. Deng, C. Zhang, C. Ruan, D. Dai, D. Chen, D. Ji, E. Li, F. Lin, F. Dai, F. Luo, G. Hao, G. Chen, G. Li, H. Zhang, H. Bao, H. Xu, H. Wang, H. Ding, H. Xin, H. Gao, H. Qu, H. Li, J. Guo, J. Li, J. Wang, J. Chen, J. Yuan, J. Qiu, J. Li, J. L. Cai, J. Ni, J. Liang, J. Chen, K. Dong, K. Hu, K. Gao, K. Guan, K. Huang, K. Yu, L. Wang, L. Zhang, L. Zhao, L. Wang, L. Zhang, L. Xu, L. Xia, M. Zhang, M. Zhang, M. Tang, M. Li, M. Wang, M. Li, N. Tian, P. Huang, P. Zhang, Q. Wang, Q. Chen, Q. Du, R. Ge, R. Zhang, R. Pan, R. Wang, R. J. Chen, R. L. Jin, R. Chen, S. Lu, S. Zhou, S. Chen, S. Ye, S. Wang, S. Yu, S. Zhou, S. Pan, S. S. Li, S. Zhou, S. Wu, S. Ye, T. Yun, T. Pei, T. Sun, T. Wang, W. Zeng, W. Zhao, W. Liu, W. Liang, W. Gao, W. Yu, W. Zhang, W. L. Xiao, W. An, X. Liu, X. Wang, X. Chen, X. Nie, X. Cheng, X. Liu, X. Xie, X. Liu, X. Yang, X. Li, X. Su, X. Lin, X. Q. Li, X. Jin, X. Shen, X. Chen, X. Sun, X. Wang, X. Song, X. Zhou, X. Wang, X. Shan, Y. K. Li, Y. Q. Wang, Y. X. Wei, Y. Zhang, Y. Xu, Y. Li, Y. Zhao, Y. Sun, Y. Wang, Y. Yu, Y. Zhang, Y. Shi, Y. Xiong, Y. He, Y. Piao, Y. Wang, Y. Tan, Y. Ma, Y. Liu, Y. Guo, Y. Ou, Y. Wang, Y. Gong, Y. Zou, Y. He, Y. Xiong, Y. Luo, Y. You, Y. Liu, Y. Zhou, Y. X. Zhu, Y. Xu, Y. Huang, Y. Li, Y. Zheng, Y. Zhu, Y. Ma, Y. Tang, Y. Zha, Y. Yan, Z. Z. Ren, Z. Ren, Z. Sha, Z. Fu, Z. Xu, Z. Xie, Z. Zhang, Z. Hao, Z. Ma, Z. Yan, Z. Wu, Z. Gu, Z. Zhu, Z. Liu, Z. Li, Z. Xie, Z. Song, Z. Pan, Z. Huang, Z. Xu, Z. Zhang, and Z. Zhang (2025)↑DeepSeek-r1: incentivizing reasoning capability in llms via reinforcement learning.
External Links: 2501.12948,
[Link](https://arxiv.org/abs/2501.12948 "")Cited by: [§1](https://arxiv.org/html/2601.12720v1#S1.p1.1 "1 Introduction ‣ Teaching Large Reasoning Models Effective Reflection"),
[§2.1](https://arxiv.org/html/2601.12720v1#S2.SS1.p1.1 "2.1 Reasoning Behaviors of LRMs ‣ 2 Related Work ‣ Teaching Large Reasoning Models Effective Reflection"),
[§2.3](https://arxiv.org/html/2601.12720v1#S2.SS3.p1.1 "2.3 Reinforcement Learning for Reasoning ‣ 2 Related Work ‣ Teaching Large Reasoning Models Effective Reflection"),
[§4](https://arxiv.org/html/2601.12720v1#S4.p4.1 "4 Experimental Methodology ‣ Teaching Large Reasoning Models Effective Reflection").

- H. Face (2025)↑Open r1: a fully open reproduction of deepseek-r1.
External Links: [Link](https://github.com/huggingface/open-r1 "")Cited by: [§3.2.1](https://arxiv.org/html/2601.12720v1#S3.SS2.SSS1.p2.3 "3.2.1 Construction of Training Data ‣ 3.2 Self-Critique Fine-Tuning (SCFT) ‣ 3 Methodology ‣ Teaching Large Reasoning Models Effective Reflection").

- K. Gandhi, A. Chakravarthy, A. Singh, N. Lile, and N. D. Goodman (2025)↑Cognitive behaviors that enable self-improving reasoners, or, four habits of highly effective stars.
External Links: 2503.01307,
[Link](https://arxiv.org/abs/2503.01307 "")Cited by: [§1](https://arxiv.org/html/2601.12720v1#S1.p2.1 "1 Introduction ‣ Teaching Large Reasoning Models Effective Reflection"),
[§2.1](https://arxiv.org/html/2601.12720v1#S2.SS1.p1.1 "2.1 Reasoning Behaviors of LRMs ‣ 2 Related Work ‣ Teaching Large Reasoning Models Effective Reflection").

- D. Hendrycks, C. Burns, S. Kadavath, A. Arora, S. Basart, E. Tang, D. Song, and J. Steinhardt (2021)↑Measuring mathematical problem solving with the math dataset.
NeurIPS.
Cited by: [§4](https://arxiv.org/html/2601.12720v1#S4.p2.1 "4 Experimental Methodology ‣ Teaching Large Reasoning Models Effective Reflection").

- T. Lan, W. Zhang, C. Lyu, S. Li, C. Xu, H. Huang, D. Lin, X. Mao, and K. Chen (2024)↑Training language models to critique with multi-agent feedback.
External Links: 2410.15287,
[Link](https://arxiv.org/abs/2410.15287 "")Cited by: [§1](https://arxiv.org/html/2601.12720v1#S1.p3.1 "1 Introduction ‣ Teaching Large Reasoning Models Effective Reflection"),
[§2.2](https://arxiv.org/html/2601.12720v1#S2.SS2.p1.1 "2.2 Critique Learning ‣ 2 Related Work ‣ Teaching Large Reasoning Models Effective Reflection").

- K. Li, Y. Tian, Q. Hu, Z. Luo, and J. Ma (2024)↑Mmcode: evaluating multi-modal code large language models with visually rich programming problems.
arXiv preprint arXiv:2404.09486.
Cited by: [§4](https://arxiv.org/html/2601.12720v1#S4.p3.1 "4 Experimental Methodology ‣ Teaching Large Reasoning Models Effective Reflection").

- H. Lightman, V. Kosaraju, Y. Burda, H. Edwards, B. Baker, T. Lee, J. Leike, J. Schulman, I. Sutskever, and K. Cobbe (2023)↑Let’s verify step by step.
External Links: 2305.20050,
[Link](https://arxiv.org/abs/2305.20050 "")Cited by: [§2.3](https://arxiv.org/html/2601.12720v1#S2.SS3.p1.1 "2.3 Reinforcement Learning for Reasoning ‣ 2 Related Work ‣ Teaching Large Reasoning Models Effective Reflection").

- Z. Liu, C. Chen, W. Li, T. Pang, C. Du, and M. Lin (2025)↑There may not be aha moment in r1-zero-like training — a pilot study.
Note: [https://oatllm.notion.site/oat-zero](https://oatllm.notion.site/oat-zero "") Notion BlogCited by: [§1](https://arxiv.org/html/2601.12720v1#S1.p2.1 "1 Introduction ‣ Teaching Large Reasoning Models Effective Reflection"),
[§2.1](https://arxiv.org/html/2601.12720v1#S2.SS1.p1.1 "2.1 Reasoning Behaviors of LRMs ‣ 2 Related Work ‣ Teaching Large Reasoning Models Effective Reflection"),
[§3.1](https://arxiv.org/html/2601.12720v1#S3.SS1.p2.1 "3.1 Effective Reflection ‣ 3 Methodology ‣ Teaching Large Reasoning Models Effective Reflection").

- M. Luo, S. Tan, J. Wong, X. Shi, W. Y. Tang, M. Roongta, C. Cai, J. Luo, L. E. Li, R. A. Popa, and I. Stoica (2025)↑DeepScaleR: surpassing o1-preview with a 1.5b model by scaling rl.
Cited by: [§2.1](https://arxiv.org/html/2601.12720v1#S2.SS1.p1.1 "2.1 Reasoning Behaviors of LRMs ‣ 2 Related Work ‣ Teaching Large Reasoning Models Effective Reflection"),
[§4](https://arxiv.org/html/2601.12720v1#S4.p2.1 "4 Experimental Methodology ‣ Teaching Large Reasoning Models Effective Reflection"),
[§4](https://arxiv.org/html/2601.12720v1#S4.p4.1 "4 Experimental Methodology ‣ Teaching Large Reasoning Models Effective Reflection").

- Z. Luo, C. Xu, P. Zhao, Q. Sun, X. Geng, W. Hu, C. Tao, J. Ma, Q. Lin, and D. Jiang (2023)↑Wizardcoder: empowering code large language models with evol-instruct.
arXiv preprint arXiv:2306.08568.
Cited by: [§4](https://arxiv.org/html/2601.12720v1#S4.p3.1 "4 Experimental Methodology ‣ Teaching Large Reasoning Models Effective Reflection").

- N. Muennighoff, Z. Yang, W. Shi, X. L. Li, L. Fei-Fei, H. Hajishirzi, L. Zettlemoyer, P. Liang, E. Candès, and T. Hashimoto (2025)↑S1: simple test-time scaling.
External Links: 2501.19393,
[Link](https://arxiv.org/abs/2501.19393 "")Cited by: [§1](https://arxiv.org/html/2601.12720v1#S1.p1.1 "1 Introduction ‣ Teaching Large Reasoning Models Effective Reflection"),
[§4](https://arxiv.org/html/2601.12720v1#S4.p4.1 "4 Experimental Methodology ‣ Teaching Large Reasoning Models Effective Reflection").

- OpenAI, :, A. Jaech, A. Kalai, A. Lerer, A. Richardson, A. El-Kishky, A. Low, A. Helyar, A. Madry, A. Beutel, A. Carney, A. Iftimie, A. Karpenko, A. T. Passos, A. Neitz, A. Prokofiev, A. Wei, A. Tam, A. Bennett, A. Kumar, A. Saraiva, A. Vallone, A. Duberstein, A. Kondrich, A. Mishchenko, A. Applebaum, A. Jiang, A. Nair, B. Zoph, B. Ghorbani, B. Rossen, B. Sokolowsky, B. Barak, B. McGrew, B. Minaiev, B. Hao, B. Baker, B. Houghton, B. McKinzie, B. Eastman, C. Lugaresi, C. Bassin, C. Hudson, C. M. Li, C. de Bourcy, C. Voss, C. Shen, C. Zhang, C. Koch, C. Orsinger, C. Hesse, C. Fischer, C. Chan, D. Roberts, D. Kappler, D. Levy, D. Selsam, D. Dohan, D. Farhi, D. Mely, D. Robinson, D. Tsipras, D. Li, D. Oprica, E. Freeman, E. Zhang, E. Wong, E. Proehl, E. Cheung, E. Mitchell, E. Wallace, E. Ritter, E. Mays, F. Wang, F. P. Such, F. Raso, F. Leoni, F. Tsimpourlas, F. Song, F. von Lohmann, F. Sulit, G. Salmon, G. Parascandolo, G. Chabot, G. Zhao, G. Brockman, G. Leclerc, H. Salman, H. Bao, H. Sheng, H. Andrin, H. Bagherinezhad, H. Ren, H. Lightman, H. W. Chung, I. Kivlichan, I. O’Connell, I. Osband, I. C. Gilaberte, I. Akkaya, I. Kostrikov, I. Sutskever, I. Kofman, J. Pachocki, J. Lennon, J. Wei, J. Harb, J. Twore, J. Feng, J. Yu, J. Weng, J. Tang, J. Yu, J. Q. Candela, J. Palermo, J. Parish, J. Heidecke, J. Hallman, J. Rizzo, J. Gordon, J. Uesato, J. Ward, J. Huizinga, J. Wang, K. Chen, K. Xiao, K. Singhal, K. Nguyen, K. Cobbe, K. Shi, K. Wood, K. Rimbach, K. Gu-Lemberg, K. Liu, K. Lu, K. Stone, K. Yu, L. Ahmad, L. Yang, L. Liu, L. Maksin, L. Ho, L. Fedus, L. Weng, L. Li, L. McCallum, L. Held, L. Kuhn, L. Kondraciuk, L. Kaiser, L. Metz, M. Boyd, M. Trebacz, M. Joglekar, M. Chen, M. Tintor, M. Meyer, M. Jones, M. Kaufer, M. Schwarzer, M. Shah, M. Yatbaz, M. Y. Guan, M. Xu, M. Yan, M. Glaese, M. Chen, M. Lampe, M. Malek, M. Wang, M. Fradin, M. McClay, M. Pavlov, M. Wang, M. Wang, M. Murati, M. Bavarian, M. Rohaninejad, N. McAleese, N. Chowdhury, N. Chowdhury, N. Ryder, N. Tezak, N. Brown, O. Nachum, O. Boiko, O. Murk, O. Watkins, P. Chao, P. Ashbourne, P. Izmailov, P. Zhokhov, R. Dias, R. Arora, R. Lin, R. G. Lopes, R. Gaon, R. Miyara, R. Leike, R. Hwang, R. Garg, R. Brown, R. James, R. Shu, R. Cheu, R. Greene, S. Jain, S. Altman, S. Toizer, S. Toyer, S. Miserendino, S. Agarwal, S. Hernandez, S. Baker, S. McKinney, S. Yan, S. Zhao, S. Hu, S. Santurkar, S. R. Chaudhuri, S. Zhang, S. Fu, S. Papay, S. Lin, S. Balaji, S. Sanjeev, S. Sidor, T. Broda, A. Clark, T. Wang, T. Gordon, T. Sanders, T. Patwardhan, T. Sottiaux, T. Degry, T. Dimson, T. Zheng, T. Garipov, T. Stasi, T. Bansal, T. Creech, T. Peterson, T. Eloundou, V. Qi, V. Kosaraju, V. Monaco, V. Pong, V. Fomenko, W. Zheng, W. Zhou, W. McCabe, W. Zaremba, Y. Dubois, Y. Lu, Y. Chen, Y. Cha, Y. Bai, Y. He, Y. Zhang, Y. Wang, Z. Shao, and Z. Li (2024)↑OpenAI o1 system card.
External Links: 2412.16720,
[Link](https://arxiv.org/abs/2412.16720 "")Cited by: [§1](https://arxiv.org/html/2601.12720v1#S1.p1.1 "1 Introduction ‣ Teaching Large Reasoning Models Effective Reflection"),
[§2.1](https://arxiv.org/html/2601.12720v1#S2.SS1.p1.1 "2.1 Reasoning Behaviors of LRMs ‣ 2 Related Work ‣ Teaching Large Reasoning Models Effective Reflection"),
[§2.3](https://arxiv.org/html/2601.12720v1#S2.SS3.p1.1 "2.3 Reinforcement Learning for Reasoning ‣ 2 Related Work ‣ Teaching Large Reasoning Models Effective Reflection").

- D. Rein, B. L. Hou, A. C. Stickland, J. Petty, R. Y. Pang, J. Dirani, J. Michael, and S. R. Bowman (2023)↑GPQA: a graduate-level google-proof qa benchmark.
External Links: 2311.12022,
[Link](https://arxiv.org/abs/2311.12022 "")Cited by: [§4](https://arxiv.org/html/2601.12720v1#S4.p2.1 "4 Experimental Methodology ‣ Teaching Large Reasoning Models Effective Reflection").

- A. R. RL Lab (2025)↑AReaL: ant reasoning rl.
GitHub.
Note: [https://github.com/inclusionAI/AReaL](https://github.com/inclusionAI/AReaL "")Cited by: [§4](https://arxiv.org/html/2601.12720v1#S4.p4.1 "4 Experimental Methodology ‣ Teaching Large Reasoning Models Effective Reflection").

- K. Team, A. Du, B. Gao, B. Xing, C. Jiang, C. Chen, C. Li, C. Xiao, C. Du, C. Liao, C. Tang, C. Wang, D. Zhang, E. Yuan, E. Lu, F. Tang, F. Sung, G. Wei, G. Lai, H. Guo, H. Zhu, H. Ding, H. Hu, H. Yang, H. Zhang, H. Yao, H. Zhao, H. Lu, H. Li, H. Yu, H. Gao, H. Zheng, H. Yuan, J. Chen, J. Guo, J. Su, J. Wang, J. Zhao, J. Zhang, J. Liu, J. Yan, J. Wu, L. Shi, L. Ye, L. Yu, M. Dong, N. Zhang, N. Ma, Q. Pan, Q. Gong, S. Liu, S. Ma, S. Wei, S. Cao, S. Huang, T. Jiang, W. Gao, W. Xiong, W. He, W. Huang, W. Wu, W. He, X. Wei, X. Jia, X. Wu, X. Xu, X. Zu, X. Zhou, X. Pan, Y. Charles, Y. Li, Y. Hu, Y. Liu, Y. Chen, Y. Wang, Y. Liu, Y. Qin, Y. Liu, Y. Yang, Y. Bao, Y. Du, Y. Wu, Y. Wang, Z. Zhou, Z. Wang, Z. Li, Z. Zhu, Z. Zhang, Z. Wang, Z. Yang, Z. Huang, Z. Huang, Z. Xu, and Z. Yang (2025)↑Kimi k1.5: scaling reinforcement learning with llms.
External Links: 2501.12599,
[Link](https://arxiv.org/abs/2501.12599 "")Cited by: [§1](https://arxiv.org/html/2601.12720v1#S1.p1.1 "1 Introduction ‣ Teaching Large Reasoning Models Effective Reflection"),
[§2.1](https://arxiv.org/html/2601.12720v1#S2.SS1.p1.1 "2.1 Reasoning Behaviors of LRMs ‣ 2 Related Work ‣ Teaching Large Reasoning Models Effective Reflection").

- O. Team (2025)↑Open Thoughts.
Note: https://open-thoughts.aiCited by: [§3.2.1](https://arxiv.org/html/2601.12720v1#S3.SS2.SSS1.p2.3 "3.2.1 Construction of Training Data ‣ 3.2 Self-Critique Fine-Tuning (SCFT) ‣ 3 Methodology ‣ Teaching Large Reasoning Models Effective Reflection").

- H. Wang, Z. Liu, S. Wang, G. Cui, N. Ding, Z. Liu, and G. Yu (2024a)↑INTERVENOR: prompting the coding ability of large language models with the interactive chain of repair.
In Findings of the Association for Computational Linguistics ACL 2024,
pp. 2081–2107.
Cited by: [§4](https://arxiv.org/html/2601.12720v1#S4.p3.1 "4 Experimental Methodology ‣ Teaching Large Reasoning Models Effective Reflection").

- P. Wang, L. Li, Z. Shao, R. X. Xu, D. Dai, Y. Li, D. Chen, Y. Wu, and Z. Sui (2024b)↑Math-shepherd: verify and reinforce llms step-by-step without human annotations.
External Links: 2312.08935,
[Link](https://arxiv.org/abs/2312.08935 "")Cited by: [§2.3](https://arxiv.org/html/2601.12720v1#S2.SS3.p1.1 "2.3 Reinforcement Learning for Reasoning ‣ 2 Related Work ‣ Teaching Large Reasoning Models Effective Reflection").

- Y. Wang, X. Yue, and W. Chen (2025)↑Critique fine-tuning: learning to critique is more effective than learning to imitate.
External Links: 2501.17703,
[Link](https://arxiv.org/abs/2501.17703 "")Cited by: [§1](https://arxiv.org/html/2601.12720v1#S1.p3.1 "1 Introduction ‣ Teaching Large Reasoning Models Effective Reflection"),
[§2.2](https://arxiv.org/html/2601.12720v1#S2.SS2.p1.1 "2.2 Critique Learning ‣ 2 Related Work ‣ Teaching Large Reasoning Models Effective Reflection").

- J. Wei, X. Wang, D. Schuurmans, M. Bosma, F. Xia, E. Chi, Q. V. Le, D. Zhou, et al. (2022)↑Chain-of-thought prompting elicits reasoning in large language models.
Advances in neural information processing systems35,  pp. 24824–24837.
Cited by: [§1](https://arxiv.org/html/2601.12720v1#S1.p1.1 "1 Introduction ‣ Teaching Large Reasoning Models Effective Reflection").

- L. Wen, Y. Cai, F. Xiao, X. He, Q. An, Z. Duan, Y. Du, J. Liu, L. Tang, X. Lv, H. Zou, Y. Deng, S. Jia, and X. Zhang (2025a)↑Light-r1: curriculum sft, dpo and rl for long cot from scratch and beyond.
External Links: 2503.10460,
[Link](https://arxiv.org/abs/2503.10460 "")Cited by: [§4](https://arxiv.org/html/2601.12720v1#S4.p4.1 "4 Experimental Methodology ‣ Teaching Large Reasoning Models Effective Reflection").

- P. Wen, J. Ji, C. Chan, J. Dai, D. Hong, Y. Yang, S. Han, and Y. Guo (2025b)↑ThinkPatterns-21k: a systematic study on the impact of thinking patterns in llms.
External Links: 2503.12918,
[Link](https://arxiv.org/abs/2503.12918 "")Cited by: [§1](https://arxiv.org/html/2601.12720v1#S1.p2.1 "1 Introduction ‣ Teaching Large Reasoning Models Effective Reflection"),
[§2.1](https://arxiv.org/html/2601.12720v1#S2.SS1.p1.1 "2.1 Reasoning Behaviors of LRMs ‣ 2 Related Work ‣ Teaching Large Reasoning Models Effective Reflection").

- Z. Xi, D. Yang, J. Huang, J. Tang, G. Li, Y. Ding, W. He, B. Hong, S. Do, W. Zhan, X. Wang, R. Zheng, T. Ji, X. Shi, Y. Zhai, R. Weng, J. Wang, X. Cai, T. Gui, Z. Wu, Q. Zhang, X. Qiu, X. Huang, and Y. Jiang (2024)↑Enhancing llm reasoning via critique models with test-time and training-time supervision.
External Links: 2411.16579,
[Link](https://arxiv.org/abs/2411.16579 "")Cited by: [§1](https://arxiv.org/html/2601.12720v1#S1.p3.1 "1 Introduction ‣ Teaching Large Reasoning Models Effective Reflection"),
[§2.2](https://arxiv.org/html/2601.12720v1#S2.SS2.p1.1 "2.2 Critique Learning ‣ 2 Related Work ‣ Teaching Large Reasoning Models Effective Reflection").

- Z. Xie, J. chen, L. Chen, W. Mao, J. Xu, and L. Kong (2025)↑Teaching language models to critique via reinforcement learning.
External Links: 2502.03492,
[Link](https://arxiv.org/abs/2502.03492 "")Cited by: [§1](https://arxiv.org/html/2601.12720v1#S1.p3.1 "1 Introduction ‣ Teaching Large Reasoning Models Effective Reflection"),
[§2.2](https://arxiv.org/html/2601.12720v1#S2.SS2.p1.1 "2.2 Critique Learning ‣ 2 Related Work ‣ Teaching Large Reasoning Models Effective Reflection").

- A. Yang, B. Zhang, B. Hui, B. Gao, B. Yu, C. Li, D. Liu, J. Tu, J. Zhou, J. Lin, K. Lu, M. Xue, R. Lin, T. Liu, X. Ren, and Z. Zhang (2024a)↑Qwen2.5-math technical report: toward mathematical expert model via self-improvement.
External Links: 2409.12122,
[Link](https://arxiv.org/abs/2409.12122 "")Cited by: [§5.3](https://arxiv.org/html/2601.12720v1#S5.SS3.p2.1 "5.3 Performance Comparison of CFT Using Different Critique Models ‣ 5 Evaluation Results ‣ Teaching Large Reasoning Models Effective Reflection").

- W. Yang, H. Wang, Z. Liu, X. Li, Y. Yan, S. Wang, Y. Gu, M. Yu, Z. Liu, and G. Yu (2024b)↑Enhancing the code debugging ability of llms via communicative agent based data refinement.
arXiv preprint arXiv:2408.05006.
Cited by: [§4](https://arxiv.org/html/2601.12720v1#S4.p3.1 "4 Experimental Methodology ‣ Teaching Large Reasoning Models Effective Reflection").

- Y. Ye, Z. Huang, Y. Xiao, E. Chern, S. Xia, and P. Liu (2025)↑LIMO: less is more for reasoning.
External Links: 2502.03387,
[Link](https://arxiv.org/abs/2502.03387 "")Cited by: [§1](https://arxiv.org/html/2601.12720v1#S1.p1.1 "1 Introduction ‣ Teaching Large Reasoning Models Effective Reflection"),
[§4](https://arxiv.org/html/2601.12720v1#S4.p2.1 "4 Experimental Methodology ‣ Teaching Large Reasoning Models Effective Reflection"),
[§4](https://arxiv.org/html/2601.12720v1#S4.p4.1 "4 Experimental Methodology ‣ Teaching Large Reasoning Models Effective Reflection").

- Q. Yu, Z. Zhang, R. Zhu, Y. Yuan, X. Zuo, Y. Yue, W. Dai, T. Fan, G. Liu, L. Liu, X. Liu, H. Lin, Z. Lin, B. Ma, G. Sheng, Y. Tong, C. Zhang, M. Zhang, W. Zhang, H. Zhu, J. Zhu, J. Chen, J. Chen, C. Wang, H. Yu, Y. Song, X. Wei, H. Zhou, J. Liu, W. Ma, Y. Zhang, L. Yan, M. Qiao, Y. Wu, and M. Wang (2025)↑DAPO: an open-source llm reinforcement learning system at scale.
External Links: 2503.14476,
[Link](https://arxiv.org/abs/2503.14476 "")Cited by: [§4](https://arxiv.org/html/2601.12720v1#S4.p2.1 "4 Experimental Methodology ‣ Teaching Large Reasoning Models Effective Reflection").

- W. Zeng, Y. Huang, Q. Liu, W. Liu, K. He, Z. Ma, and J. He (2025)↑SimpleRL-zoo: investigating and taming zero reinforcement learning for open base models in the wild.
External Links: 2503.18892,
[Link](https://arxiv.org/abs/2503.18892 "")Cited by: [§1](https://arxiv.org/html/2601.12720v1#S1.p1.1 "1 Introduction ‣ Teaching Large Reasoning Models Effective Reflection"),
[§2.1](https://arxiv.org/html/2601.12720v1#S2.SS1.p1.1 "2.1 Reasoning Behaviors of LRMs ‣ 2 Related Work ‣ Teaching Large Reasoning Models Effective Reflection"),
[§4](https://arxiv.org/html/2601.12720v1#S4.p4.1 "4 Experimental Methodology ‣ Teaching Large Reasoning Models Effective Reflection").

- Y. Zheng, R. Zhang, J. Zhang, Y. Ye, Z. Luo, Z. Feng, and Y. Ma (2024)↑LlamaFactory: unified efficient fine-tuning of 100+ language models.
In Proceedings of the 62nd Annual Meeting of the Association for Computational Linguistics (Volume 3: System Demonstrations),
Bangkok, Thailand.
External Links: [Link](http://arxiv.org/abs/2403.13372 "")Cited by: [§4](https://arxiv.org/html/2601.12720v1#S4.p5.5 "4 Experimental Methodology ‣ Teaching Large Reasoning Models Effective Reflection").


## Appendix A Appendix

Report issue for preceding element

### A.1 Reflection Evaluation Prompt

Report issue for preceding element

We use the following prompt to evaluate the quality of the model’s self-reflection within a complete reasoning trajectory. The evaluator is tasked with identifying reflection moments and scoring their effectiveness based on the defined principles.

Report issue for preceding element

System Prompt for Trajectory-Level Reflection ScoringSystem Prompt:
You are an expert Mathematics and Logic Evaluator.
Your task is to assess the quality of the \*\*Self-Reflection/Critique\*\* mechanisms within a model’s reasoning trajectory.Input Data:•Question: \[Insert Question\]•Model Trajectory: \[Insert the full Chain-of-Thought generated by the model\]Evaluation Process:1.Locate Reflection: Scan the trajectory for moments where the model pauses to verify, critique, or correct itself (e.g., keywords like “Wait”, “Let me double check”, “Hold on”, or specific tags).2.Verify Logic: Independently verify the math/logic at the point of reflection. Determine if the model’s previous step was actually correct or incorrect.3.Apply Principles: Evaluate the reflection using the 5 Principles (P1P\_{1}-P5P\_{5}).Scoring Rubric (0-10 Scale):•Score 0-2 (Harmful/Hallucinated - P1P\_{1} Failed):
The model performs a “Fake Reflection”.–It claims a correct step is wrong (Hallucination).–It confirms a wrong step is correct (Sycophancy).–Penalty: If P1P\_{1} is violated, the score must be ≤2\\leq 2, regardless of length.•Score 3-5 (Superficial/Ineffective):
The model attempts to reflect but fails to add value.–It says “Let me check” and simply repeats the same wrong logic.–It identifies an error but fails to fix it (P2P\_{2} failed).–The reflection is vague (e.g., “Something is wrong”) without specificity (P3P\_{3} failed).•Score 6-8 (Effective Correction):
The reflection successfully identifies and fixes an error.–The model correctly spots a calculation or logic error (P1,P3P\_{1},P\_{3}).–It proposes a valid correction that steers the trajectory back to the right path (P2P\_{2}).•Score 9-10 (Profound Insight):
The reflection demonstrates high-level reasoning capabilities.–It uses a different method to verify the answer (Rigorous Verification - P4P\_{4}).–It breaks a logical loop or provides a shortcut that significantly simplifies the problem (High InfoGain - P5P\_{5}).Output Format:
Return a JSON object with the analysis and final score.

{

"reflection\_moments": \["Wait, I missed the coefficient of xˆ2 in the expansion..."\],

"analysis": "The model correctly identified a calculation error.It verified this by re-calculating and provided the correct value, leading to the right answer.",

"score": 8

}
Report issue for preceding element

|     |
| --- |
| Instruction:Please critique whether the following solution to the question is correct.Question: From an external point AA, a tangent A​BAB and a secant A​C​DACD are drawn to a circle. Find the area of triangle C​B​DCBD, given that the ratio A​C:A​B=2:3AC:AB=2:3 and the area of triangle A​B​CABC is 20.Solution: Okay, so I have this geometry problem where an external point A is drawing a tangent AB and a secant ACD to a circle. The ratio of AC to AB is 2:3, and the area of triangle ABC is 20. I need to find the area of triangle CBD. Hmm, let me think about how to approach this.First, let me try to visualize the problem. There’s a circle…Given the ratio AC:AB = 2:3. That tells me that AB is longer than AC. Specifically, if AC is 2x, then AB is 3x for some value x. I also know that the area of triangle ABC is 20. I need to find the area of triangle CBD.…(3​x)2=2​x×A​D(3x)^{2}=2x\\times AD9​x2=2​x×A​D9x^{2}=2x\\times ADA​D=9​x22​x=9​x2AD=\\frac{9x^{2}}{2x}=\\frac{9x}{2}Since A​D=A​C+C​DAD=AC+CD, we find C​DCD:C​D=A​D−A​C=9​x2−2​x=9​x2−4​x2=5​x2CD=AD-AC=\\frac{9x}{2}-2x=\\frac{9x}{2}-\\frac{4x}{2}=\\frac{5x}{2}Next, we use the fact that the areas of triangles sharing the same height are proportional to their bases. Triangles A​B​CABC and C​B​DCBD share the same height from vertex BB to the bases A​CAC and C​DCD respectively. Therefore, the ratio of their areas is the ratio of their bases A​CAC and C​DCD:Ratio of areas=A​CC​D=2​x5​x2=45\\text{Ratio of areas}=\\frac{AC}{CD}=\\frac{2x}{\\frac{5x}{2}}=\\frac{4}{5}Given the area of triangle A​B​CABC is 20, the area of triangle C​B​DCBD is:Area of ​△​C​B​D=45×20=16\\text{Area of }\\triangle CBD=\\frac{4}{5}\\times 20=16Thus, the area of triangle C​B​DCBD is 16\\boxed{16}.\- \- \- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -Response:<think><br>Okay, so I need to evaluate the solution provided for the given math problem. Let me start by understanding the problem again.The proposed solution uses the Power of a Point theorem, the ratio of lengths, and then the ratio of areas to conclude that the area of triangle CBD is 16. The user is asking if the solution is correct, if not, to explain why and provide a refined solution.…Now, considering triangles ABC and CBD. Both triangles share the same vertex B and their bases AC and CD lie on the same line AD. The key here is that they share the same height from point B to the line AD. Therefore, the ratio of their areas is equal to the ratio of their bases:Ratio of areas=Area of ABCArea of CBD=A​CC​D\\text{Ratio of areas}=\\frac{\\text{Area of ABC}}{\\text{Area of CBD}}=\\frac{AC}{CD}Substituting the values of AC and CD:Area of ABCArea of CBD=2​x5​x2=45\\frac{\\text{Area of ABC}}{\\text{Area of CBD}}=\\frac{2x}{\\frac{5x}{2}}=\\frac{4}{5}Given that the area of triangle ABC is 20:20Area of CBD=45\\frac{20}{\\text{Area of CBD}}=\\frac{4}{5}Area of CBD=20×54=25\\text{Area of CBD}=20\\times\\frac{5}{4}=25Wait, hold on. My previous conclusion was 16, but upon recalculating using the correct ratio, it’s 25. There must be a mistake in the initial reasoning.<br>…I realize now that in the initial solution, the ratio was incorrectly interpreted as 4/5, leading to an answer of 16, but in reality, the ratio of AC to CD is 4:5, so CBD’s area should be larger than ABC’s.Therefore, the correct area of triangle CBD is 25.\*\*Final Answer\*\*<br>The area of triangle C​B​DCBD is 25.</think>Given an external point AA from which a tangent A​BAB and a secant A​C​DACD are drawn to a circle, we know the ratio A​C:A​B=2:3AC:AB=2:3 and the area of triangle A​B​CABC is 20. We need to find the area of triangle C​B​DCBD.First, we use the Power …<br>Next, we use the fact that triangles A​B​CABC and C​B​DCBD share the same height from vertex BB to the bases A​CAC and C​DCD respectively. Therefore, the ratio of their areas is equal to the ratio of their bases:Ratio of areas=Area of ABCArea of CBD=A​CC​D\\text{Ratio of areas}=\\frac{\\text{Area of ABC}}{\\text{Area of CBD}}=\\frac{AC}{CD}Substituting the values of A​CAC and C​DCD:Area of ABCArea of CBD=2​x5​x2=45\\frac{\\text{Area of ABC}}{\\text{Area of CBD}}=\\frac{2x}{\\frac{5x}{2}}=\\frac{4}{5}Given that the area of triangle A​B​CABC is 20:20Area of CBD=45\\frac{20}{\\text{Area of CBD}}=\\frac{4}{5}Area of CBD=20×54=25\\text{Area of CBD}=20\\times\\frac{5}{4}=25Thus, the area of triangle C​B​DCBD is 25. |

Table 5: A Training Example.Report issue for preceding element

### A.2 Example of Training Data

Report issue for preceding element

As shown in Table [5](https://arxiv.org/html/2601.12720v1#A1.T5 "Table 5 ‣ A.1 Reflection Evaluation Prompt ‣ Appendix A Appendix ‣ Teaching Large Reasoning Models Effective Reflection"), we present an example of the training data used in self-critique fine-tuning.

Report issue for preceding element

### A.3 Additional Performance Analysis

Report issue for preceding element![Refer to caption](https://arxiv.org/html/2601.12720v1/x6.png)Figure 5: The Pass@16 results of different models. “Base” represents the model that has not been fine-tuned, and “SD” and “SC” respectively represent the models fine-tuned through Self-Distill and Self-Critique Fine-tuning.Report issue for preceding element

In this section, we provide further analysis of the model performance using the Pass@16 metric.

Report issue for preceding element

As shown in Figure [5](https://arxiv.org/html/2601.12720v1#A1.F5 "Figure 5 ‣ A.3 Additional Performance Analysis ‣ Appendix A Appendix ‣ Teaching Large Reasoning Models Effective Reflection"), we show Pass@16 results for different models. From the results, we can observe that the models fine-tuned with Self-Critique Fine-Tuning (SCFT) consistently outperform their self-distillation counterparts across all datasets. Across models of different scales, SCFT brings an average improvement of 3.1%. These improvements further demonstrate that SCFT is an effective technique for enhancing model performance.

Report issue for preceding element

### A.4 Case Studies

Report issue for preceding element

Finally, we show cases in Table [6](https://arxiv.org/html/2601.12720v1#A1.T6 "Table 6 ‣ A.4 Case Studies ‣ Appendix A Appendix ‣ Teaching Large Reasoning Models Effective Reflection") to demonstrate that SCFT+RLERR can teach models reflective behavior in reasoning.
Overall, the response of the model after training can effectively self-reflect within shorter responses and generate correct answers. From the case, we can see that DeepSeek-R1-Distill-Qwen-7B introduces an error (b=5b=5) into the originally correct answer (b=211b=211). It considers the wrong answer to be correct and uses 32,225 tokens for reasoning. On the contrary, our model can do correct reflection with fewer reasoning tokens and confirm the correct answer. SCFT+RLERR shows its effectiveness in teaching models to identify and correct their own mistakes efficiently.

Report issue for preceding element

|     |
| --- |
| Question (gt = 211): Let b≥2b\\geq 2 be an integer. Call a positive integer nnb​-eautifulb\\text{-}\\textit{eautiful} if it has exactly two digits when expressed in base bb and these two digits sum to n\\sqrt{n}. For example, 8181 is 13​-eautiful13\\text{-}\\textit{eautiful} because 81=6¯​3¯1381=\\underline{6}\ \\underline{3}\_{13} and 6+3=816+3=\\sqrt{81}. Find the least integer b≥2b\\geq 2 for which there are more than ten b​-eautifulb\\text{-}\\textit{eautiful} integers.\- \- \- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -<br>DeepSeek-R1-Distill-Qwen-7B: Okay, so I need to find the least integer b≥2b\\geq 2, … Hence, b−1b-1 must have at least four distinct prime factors. The smallest such b−1b-1 is 2×3×5×7=2102\\times 3\\times 5\\times 7=210, so b=211b=211. ✓But wait, let’s confirm for b=211b=211, b−1=210b-1=210. The number of solutions ss is 24=162^{4}=16. So, 16 numbers. But wait, in our earlier case, for b=13b=13, which had b−1=12b-1=12, which has two prime factors, 2 and 3, we had two solutions…Wait, this is conflicting. So, maybe my formula is incorrect… So, let’s compute (b2+b−1b−1)\\dbinom{b^{2}+b-1}{b-1}for increasing bb until it exceeds1000. Compute for b=2b=2:<br>… b=5b=5:… Wait, hold on, let me compute: b=5b=5: b2+b−1=25+5−1=29b^{2}+b-1=25+5-1=29. Compute (294)=29∗28∗27∗264∗3∗2∗1=29∗28∗27∗2624\\dbinom{29}{4}=\\frac{29\*28\*27\*26}{4\*3\*2\*1}=\\frac{29\*28\*27\*26}{24}… So, (294)=23751\\dbinom{29}{4}=23751, which is greater than1000.Therefore, for b=5b=5, the number exceeds1000. But wait, is b=5b=5 the minimal? let me check b=4b=4: 969 <1000. So, the minimal bb is 5✗… But let me verify for b=4b=4:969<1000, so indeed, b=5b=5 is the minimal.✗(32225 tokens)\- \- \- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -Our Model: Okay, so I need to solve this math problem … Let me break this down step by step. First, … But the problem says "the least integer b≥2b\\geq 2 for which there are more than ten bb-eautiful integers." So, 211 might be the answer ✓, but that seems too large, and the problem is likely expecting a smaller answer.Wait, perhaps my entire approach is wrong. Let me think again.<br>let me verify for b=13b=13. Earlier, I found 3 solutions, but perhaps I missed some. s=4,9,12. Is that all? Check s=3: 3\*2=6. 12 divides 6? No. s=5:5\*4=20. 12 divides 20? … So, only 3 solutions. So, with ω=2\\omega=2, only 3 solutions, which is less than 7 with ω=3\\omega=3. So, it’s not a linear relationship. Therefore, the number of solutions doesn’t scale exactly with ω\\omega. Hence, my conclusion that b=211b=211 is correct, despite it being large. ✓(14556 tokens) |

Table 6: Case Studies. Our model undergoes effective reflection and provides the correct answer. The blue text represents reflection, and the green/red text respectively represent obtaining the correct/wrong answers.Report issue for preceding element

Report IssueReport Issue for Selection

Generated by
[L\\
A\\
T\\
Exml![[LOGO]](<Base64-Image-Removed>)](https://math.nist.gov/~BMiller/LaTeXML/)