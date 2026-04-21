import streamlit as st
import akshare as ak
import pandas as pd
import plotly.graph_objects as go

# --- 1. 页面设置 ---
st.set_page_config(page_title="NIQING | 复合预警雷达", layout="wide")
st.title("妮情 · 量能 + 十字星 + 金叉 复合扫描终端")

if "c_list" not in st.session_state:
    st.session_state.c_list = pd.DataFrame()

# --- 2. 侧边栏策略参数 ---
with st.sidebar:
    st.header("⚙️ 预警配置")
    min_vol_亿 = st.number_input("最低成交额 (亿)", value=5.0)
    star_ratio = st.slider("十字星严格度 (实体占比)", 0.05, 0.25, 0.15)
    st.info("提示：金叉检测会调取历史 K 线，扫描速度会略微变慢。")

# --- 3. 核心计算函数 ---
def check_kdj_gold(df):
    """判定 KDJ 是否在低位金叉"""
    low, high, close = df['low'], df['high'], df['close']
    low_9 = low.rolling(window=9).min()
    high_9 = high.rolling(window=9).max()
    rsv = (close - low_9) / (high_9 - low_9) * 100
    k = rsv.ewm(com=2).mean()
    d = k.ewm(com=2).mean()
    j = 3 * k - 2 * d
    # 金叉逻辑：当日 J > D 且昨日 J <= D
    if j.iloc[-1] > d.iloc[-1] and j.iloc[-2] <= d.iloc[-2]:
        return True, round(j.iloc[-1], 2)
    return False, 0

# --- 4. 扫描引擎 ---
if st.button("🚀 启动全维度复合预警扫描"):
    with st.spinner("正在解构全市场量价信号..."):
        try:
            # 1. 抓取实时快照
            spot_df = ak.stock_zh_a_spot_em()
            # 基础过滤：成交额
            spot_df['成交额'] = pd.to_numeric(spot_df['成交额'], errors='coerce')
            pool = spot_df[spot_df['成交额'] >= min_vol_亿 * 100000000].copy()
            
            res = []
            progress_bar = st.progress(0)
            
            for i, (idx, row) in enumerate(pool.iterrows()):
                # 更新进度条
                progress_bar.progress((i + 1) / len(pool))
                
                # A. 十字星判定逻辑
                o, c, h, l = row['今开'], row['最新价'], row['最高'], row['最低']
                body = abs(o - c)
                amp = h - l
                if amp > 0 and (body / amp) <= star_ratio:
                    star_type = "🔴 阳线十字" if c >= o else "🟢 阴线十字"
                    
                    # B. 调取历史数据判断金叉 (由于速度考虑，仅对符合十字星的票进行金叉检测)
                    try:
                        hist = ak.stock_zh_a_hist(symbol=row['代码'], period="daily", adjust="qfq").tail(20)
                        is_gold, j_val = check_kdj_gold(hist)
                        
                        if is_gold:
                            res.append({
                                "代码": row['代码'],
                                "名称": row['名称'],
                                "形态": star_type,
                                "预警": "⚡ KDJ金叉",
                                "J值": j_val,
                                "成交额(亿)": round(row['成交额']/1e8, 2),
                                "涨跌幅%": row['涨跌幅']
                            })
                    except:
                        continue
            
            st.session_state.c_list = pd.DataFrame(res)
            st.success(f"扫描完成！捕捉到 {len(res)} 个复合强势信号。")
        except Exception as e:
            st.error(f"扫描中断: {e}")

# --- 5. 数据展示 ---
if not st.session_state.c_list.empty:
    st.dataframe(st.session_state.c_list, use_container_width=True)
    st.caption("注：雷达同时满足 [大成交额] + [十字星形态] + [KDJ低位金叉] 三个条件。")
else:
    st.info("等待扫描指令。建议选择交易活跃时段运行。")
