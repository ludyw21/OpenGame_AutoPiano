# 无线传播实验报告（原理部分，Markdown）

## I. 引言（Introduction）
无线通信链路的覆盖与性能由发射机、天线、无线信道以及接收机共同决定。实际环境中，电磁波在传播过程中受到距离衰减、阴影遮蔽与多径效应的共同作用，表现为接收场强/功率的显著起伏。为实现可靠接收，接收点需处于有效覆盖区，且接收功率不低于接收机灵敏度门限，并留有足够衰落裕量。本文在国际论文常见写法下，给出室内外典型传播机理与相应公式，作为实验设计与结果分析的理论依据。

## II. 系统与信道模型（System and Channel Model）
- 无线链路构成：发射机、发射天线、无线信道、接收天线、接收机。
- 覆盖条件：Pr ≥ S（接收功率不低于灵敏度），并预留 Fade Margin。
- 链路预算（dB）  
  Pr = Pt + Gt + Gr − Lfs − Lpen − Lm
- 接收机灵敏度（dBm）  
  S = 10·log10(kTB/1 mW) + NF + SNRmin

其中：Pt 为发射功率，Gt/Gr 为发/收天线增益，Lfs 为自由空间路径损耗，Lpen 为穿透损耗，Lm 为其它损耗（馈线、极化失配、人体遮挡等），k 为玻尔兹曼常数，T 为噪声温度，B 为带宽，NF 为噪声系数，SNRmin 为最小可解调信噪比。

## III. 传播与损耗模型（Propagation and Loss Models）

### A. 自由空间与大尺度路径损耗
- 自由空间路径损耗（FSPL, dB）  
  Lfs = 32.44 + 20·log10(fMHz) + 20·log10(dkm)
- 对数距离路径损耗模型（含阴影衰落）  
  PL(d) = PL(d0) + 10·n·log10(d/d0) + Xσ  
  其中 n 为路径损耗指数，Xσ ~ N(0, σ²)（dB）表征阴影衰落。

### B. 室外经验模型（示例）
- Okumura–Hata（城市, 150–1500 MHz）  
  PL(dB) = 69.55 + 26.16·log10(fMHz) − 13.82·log10(hb) − a(hr)  
  + [44.9 − 6.55·log10(hb)]·log10(dkm)
- COST-231 Hata（至约 2.1 GHz）  
  PL(dB) = 46.3 + 33.9·log10(fMHz) − 13.82·log10(hb) − a(hr)  
  + [44.9 − 6.55·log10(hb)]·log10(dkm) + C

其中 hb/hr 分别为发射/接收天线高度，a(hr) 为高度修正项，C 为城市场景常数。

### C. 室内多墙/楼板模型
- COST-231 多墙模型  
  PL(d) = PL(d0) + 10·n·log10(d/d0) + ΣW_i + ΣF_j + Xσ  
  其中 ΣW_i 为各类墙体附加损耗之和，ΣF_j 为楼板穿越损耗之和。

### D. 建筑物穿透损耗
- 定义（在相同单位下）  
  Lpen = Eout − Ein = Pout − Pin
- 分层近似模型  
  Lpen ≈ L0 + k·Nlayers

Eout/Ein 为室外/室内中值场强或功率；L0 为基础穿透损耗；k 为单位层/材料等效系数。

## IV. 小尺度衰落与多径效应（Small-Scale Fading and Multipath）

### A. 统计幅度分布
- NLOS（无直射）瑞利分布  
  pR(r) = (r/σ²)·exp(−r²/(2σ²)), r ≥ 0
- LOS（有直射）莱斯分布  
  pR(r) = (r/σ²)·exp(−(r² + s²)/(2σ²))·I0(rs/σ²), r ≥ 0  
  K 因子：K = s²/(2σ²)，K[dB] = 10·log10(K)

### B. 时频选择性与时间选择性
- 均方根时延扩展  
  τRMS = sqrt( (Σ Pi(τi − τ̄)²)/(Σ Pi) ), 其中 τ̄ = (Σ Piτi)/(Σ Pi)
- 相干带宽（近似）  
  Bc ≈ 1/(5·τRMS)
- 最大多普勒与相干时间  
  fD = v·fc/c,  Tc ≈ 1/(2·fD)

当信号带宽 > Bc 时产生频率选择性衰落；移动导致随时间快速起伏。

## V. 干扰、噪声与链路质量（Interference, Noise, and Link Quality）
- SINR 定义  
  SINR = Ps/(I + N)
- 噪声功率（dBm）  
  N = 10·log10(kTB/1 mW) + NF
- 极化失配损耗  
  Lpol = −20·log10(|êt · êr|)
- 天线有效孔径与增益  
  Ae = (λ²·G)/(4π)

## VI. 可靠性与参数估计（Reliability and Parameter Estimation）
- 衰落裕量（Fade Margin）  
  FM = Pr,avg − S − Mreq  
  其中 Mreq 由目标覆盖概率与阴影标准差 σ 确定。
- 路径损耗指数最小二乘估计  
  设 yi = PL(di) − PL(d0)，xi = log10(di/d0)，则  
  n̂ = (Σ xiyi)/(10·Σ xi²)
- 阴影衰落标准差估计  
  σ̂ = std{ yi − 10·n̂·xi }

——  
说明：上述原理与公式覆盖室外宏/微蜂窝、街峡场景与室内办公/走廊/跨楼层等典型环境。实际实验中应依据频段、天线高度、材料参数与统计样本量选择相应模型与系数，并采用一致单位体系（dBm 或 dBμV/m）呈现与拟合。
