import streamlit as st
import akshare as ak
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time
import random

# --- 1. 终端视觉与初始化 ---
st.set_page_config(page_title="NIQING | 量能雷达", layout="wide")
st.markdown("<style>.stApp { background-color: #0b0e14; color: #e0e0e0; }</style>", unsafe_allow_html=True)

# 确保 session 状态存在，防止 KeyError
if "g_list" not in st.session_state: st.session_state.g_list = pd.DataFrame()
if "c_list" not in st.session_state: st.session_state.c_list = pd.DataFrame()

# --- 2. 授权验证 ---
if "auth" not in st.session_state:
    st.markdown("<h2 style='text-align: center; color: #d4af37;'>NIQING STUDIO 策略终端</h2>", unsafe_allow_html=True)
    if st.text_input("授权令牌", type="password") == "niqing888":
        st.session_state.auth = True
        st.rerun()
    st.stop()

# --- 3. 核心计算引擎 ---
class NIQINGEngine:
    @staticmethod
    def safe_fetch(func, **kwargs):
        """带重试的数据抓取"""
        for _ in range(3):
            try:
                time.sleep(random.uniform(0.2, 0.4))
                return func(**kwargs)
            except: time.sleep(1)
        return pd.DataFrame()

    @staticmethod
    def is_green_cross(row, sens=0.15):
        """判定绿色十字星"""
        if row['今开'] <= row['最新价']: return False  # 必须是阴线
        entity = abs(row['今开'] - row['最新价'])
        total_range = row['最高'] - row['最低'] + 0.001
        return (entity / total_range) <= sens

    @staticmethod
    def check_kdj_gold(code):
        """判定KDJ金叉"""
        try:
            df = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq").tail(20)
            if len(df) < 10: return False
            low_9, high_9 = df['最低'].rolling(9).min(), df['最高'].rolling(9).max()
            rsv = (df['收盘'] - low_9) / (high_9 - low_9 + 0.001) * 100
            df['K'] = rsv.ewm(com=2, adjust=False).mean()
            df['D'] = df['K'].ewm(com=2, adjust=False).mean()
            return (df.iloc[-2]['K'] < df.iloc[-2]['D']) and (df.iloc[-1]['K'] > df.iloc[-1]['D'])
        except: return False

# --- 4. 侧边栏配置 ---
with st.sidebar:
    st.header("⚙️ 扫描配置")
    scan_num = st.slider("扫描活跃股数量", 50, 300, 100)
    cross_sens = st.slider("十字星灵敏度", 0.05, 0.3, 0.15)
    min_vol = st.number_input("最小成交额(万)", value=10000)

st.title("妮情 · 量能信号实时全自动雷达")

# --- 5. 执行自动扫描 ---
if st.button("🚀 启动全市场【量能+形态】深度扫描"):
    with st.spinner("正在同步全市场实时行情并分析量能..."):
        all_stocks = NIQINGEngine.safe_fetch(ak.stock_zh_a_spot_em)
        if not all_stocks.empty:
            # 统一字段类型
            num_cols = ['最新价', '涨跌幅', '成交量', '成交额', '最高', '最低', '今开']
            all_stocks[num_cols] = all_stocks[num_cols].apply(pd.to_numeric, errors='coerce')
            
            # 筛选高成交活跃池
            pool = all_stocks[all_stocks['成交额'] >= min_vol * 10000].sort_values('成交额', ascending=False).head(scan_num)
            
            g_results, c_results = [], []
            progress = st.progress(0)
            status = st.empty()

            for i, (idx, row) in enumerate(pool.iterrows()):
                status.text(f"深度扫描中: {row['名称']} ({i+1}/{len(pool)})")
                
                info = {
                    "代码": row['代码'], "名称": row['名称'], 
                    "涨跌幅%": row['涨跌幅'], "最新价": row['最新价'],
                    "成交量(手)": int(row['成交量']), 
                    "成交额(亿)": round(row['成交额']/1e8, 2)
                }

                # 检测形态
                if NIQINGEngine.is_green_cross(row, cross_sens): c_results.append(info)
                if NIQINGEngine.check_kdj_gold(row['代码']): g_results.append(info)
                
                progress.progress((i + 1) / len(pool))
            
            st.session_state.g_list = pd.DataFrame(g_results)
            st.session_state.c_list = pd.DataFrame(c_results)
            status.success(f"扫描完毕！发现金叉 {len(g_results)} 个，十字星 {len(c_results)} 个。")

# --- 6. 结果双屏与成交量展示 ---
col_left, col_right = st.columns(2)

with col_left:
    st.markdown("### 📈 今日 KDJ 金叉 (带成交量)")
    st.dataframe(st.session_state.g_list, use_container_width=True, height=350)

with col_right:
    st.markdown("### 💹 今日绿色十字星 (带成交量)")
    st.dataframe(st.session_state.c_list, use_container_width=True, height=350)

# --- 7. 深度量价透视窗口 ---
st.divider()
st.subheader("🔍 选定个股深度量价回测")

# 安全提取名称列表进行合并
all_names = []
if not st.session_state.g_list.empty: all_names += st.session_state.g_list['名称'].tolist()
if not st.session_state.c_list.empty: all_names += st.session_state.c_list['名称'].tolist()
all_names = list(set(all_names))

if all_names:
    selected = st.selectbox("选择股票查看【K线+量能】详情", all_names)
    # 获取对应代码
    combined = pd.concat([st.session_state.g_list, st.session_state.c_list])
    target_code = combined[combined['名称'] == selected]['代码'].values[0]
    
    h_df = NIQINGEngine.safe_fetch(ak.stock_zh_a_hist, symbol=target_code, adjust="qfq").tail(60)
    
    # 绘图：三层架构 (价格+量能+指标)
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.7, 0.3])
    fig.add_trace(go.Candlestick(x=h_df['日期'], open=h_df['开盘'], high=h_df['最高'], low=h_df['最低'], close=h_df['收盘'], name="K线"), row=1, col=1)
    
    # 成交量颜色随阴阳变动
    v_colors = ['#2ecc71' if c > o else '#e74c3c' for c, o in zip(h_df['收盘'], h_df['开盘'])]
    fig.add_trace(go.Bar(x=h_df['日期'], y=h_df['成交量'], marker_color=v_colors, name="成交量"), row=2, col=1)
    
    fig.update_layout(height=650, template="plotly_dark", xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("完成上方扫描后即可查看个股详情。")
