import streamlit as st
import akshare as ak
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time
import random

# --- 1. 终端配置 ---
st.set_page_config(page_title="NIQING | 全自动扫描终端", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #0b0e14; color: #e0e0e0; }
    .stButton>button { border: 1px solid #d4af37; color: #d4af37; background: transparent; width: 100%; height: 3em; font-size: 20px; }
    .stButton>button:hover { background-color: #d4af37; color: black; border: 1px solid #d4af37; }
    .gold-text { color: #d4af37; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 授权验证 ---
if "auth" not in st.session_state:
    st.markdown("<h2 style='text-align: center; color: #d4af37;'>NIQING STUDIO 策略终端</h2>", unsafe_allow_html=True)
    if st.text_input("授权令牌", type="password") == "niqing888":
        st.session_state.auth = True
        st.rerun()
    st.stop()

# --- 3. 高性能扫描引擎 ---
class NIQINGScanner:
    @staticmethod
    def get_kdj_signal(code):
        """单只股票金叉判定逻辑"""
        try:
            # 抓取最近30天数据即可，提高速度
            df = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq").tail(30)
            if len(df) < 10: return False
            
            low_9 = df['最低'].rolling(9).min()
            high_9 = df['最高'].rolling(9).max()
            rsv = (df['收盘'] - low_9) / (high_9 - low_9 + 0.001) * 100
            df['K'] = rsv.ewm(com=2, adjust=False).mean()
            df['D'] = df['K'].ewm(com=2, adjust=False).mean()
            
            last = df.iloc[-1]
            prev = df.iloc[-2]
            # 判定：昨日K<D 且 今日K>D
            return (prev['K'] < prev['D']) and (last['K'] > last['D'])
        except:
            return False

# --- 4. UI 交互布局 ---
st.title("妮情 · 今日金叉全自动雷达")

# 侧边栏参数控制
st.sidebar.header("⚙️ 扫描过滤参数")
min_vol = st.sidebar.number_input("最小成交额 (万元)", value=10000, step=1000)
min_pct = st.sidebar.slider("今日最低涨幅 (%)", -2.0, 5.0, 0.0)
max_scan = st.sidebar.slider("最大扫描数量", 50, 300, 100, help="为了防止被封IP，建议先扫活跃的前100只")

if st.button("🚀 启动全市场金叉自动扫描"):
    with st.spinner("正在同步全市场实时行情..."):
        # 1. 获取全 A 股快照
        all_stocks = ak.stock_zh_a_spot_em()
        if not all_stocks.empty:
            # 2. 初步筛选：按成交额和涨幅过滤掉“僵尸股”
            all_stocks[['最新价', '涨跌幅', '成交额']] = all_stocks[['最新价', '涨跌幅', '成交额']].apply(pd.to_numeric, errors='coerce')
            filtered = all_stocks[
                (all_stocks['成交额'] >= min_vol * 10000) & 
                (all_stocks['涨跌幅'] >= min_pct)
            ].sort_values('成交额', ascending=False).head(max_scan)
            
            st.info(f"符合初步筛选条件共 {len(filtered)} 只，开始深度扫描 KDJ 指标...")
            
            # 3. 循环判定金叉
            golden_list = []
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for i, (idx, row) in enumerate(filtered.iterrows()):
                status_text.text(f"正在分析: {row['名称']} ({i+1}/{len(filtered)})")
                if NIQINGScanner.get_kdj_signal(row['代码']):
                    golden_list.append({
                        "代码": row['代码'],
                        "名称": row['名称'],
                        "最新价": row['最新价'],
                        "涨跌幅%": row['涨跌幅'],
                        "成交额(亿)": round(row['成交额']/1e8, 2)
                    })
                progress_bar.progress((i + 1) / len(filtered))
                time.sleep(0.1) # 微小延迟保护IP
            
            st.session_state.golden_results = pd.DataFrame(golden_list)
            status_text.success(f"扫描完成！今日共捕捉到 {len(golden_list)} 只金叉股。")
        else:
            st.error("无法连接到行情中心")

# --- 5. 结果展示 ---
if "golden_results" in st.session_state and not st.session_state.golden_results.empty:
    st.markdown("### 🎯 今日金叉信号池")
    # 使用 dataframe 展示结果
    selected_stock = st.selectbox("点击下方列表中的股票查看详情图表", st.session_state.golden_results['名称'].tolist())
    
    st.table(st.session_state.golden_results)
    
    # 联动展示选中的图表
    if selected_stock:
        target_code = st.session_state.golden_results[st.session_state.golden_results['名称'] == selected_stock]['代码'].values[0]
        h_df = ak.stock_zh_a_hist(symbol=target_code, adjust="qfq").tail(60)
        
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3])
        fig.add_trace(go.Candlestick(x=h_df['日期'], open=h_df['开盘'], high=h_df['最高'], low=h_df['最低'], close=h_df['收盘'], name="K线"), row=1, col=1)
        fig.update_layout(height=500, template="plotly_dark", xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)
elif "golden_results" in st.session_state:
    st.warning("完成扫描，但未发现符合条件的金叉股票。")
