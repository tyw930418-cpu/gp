import streamlit as st
import akshare as ak
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

# ==========================================
# 第一部分：产品化配置与加密访问
# ==========================================
st.set_page_config(
    page_title="NIQING STUDIO | 股票策略终端",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 简单的访问加密逻辑
def check_password():
    """返回 True 如果用户输入了正确的密码"""
    def password_entered():
        if st.session_state["password"] == "niqing888": # 这里设置你的分享密码
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.markdown("<h2 style='text-align: center; color: #d4af37;'>NIQING STUDIO 策略终端</h2>", unsafe_allow_html=True)
        st.text_input("请输入授权令牌以开启终端", type="password", on_change=password_entered, key="password")
        st.info("授权请联系：NIQING STUDIO 管理员")
        return False
    elif not st.session_state["password_correct"]:
        st.text_input("令牌错误，请重新输入", type="password", on_change=password_entered, key="password")
        st.error("❌ 访问受限")
        return False
    else:
        return True

if not check_password():
    st.stop()

# ==========================================
# 第二部分：黑金旗舰视觉注入
# ==========================================
st.markdown("""
    <style>
    /* 核心背景与字体 */
    .stApp { background-color: #0b0e14; color: #e0e0e0; }
    /* 指标卡片样式 */
    [data-testid="stMetricValue"] { color: #d4af37 !important; font-family: 'Courier New', monospace; }
    /* 按钮样式 */
    .stButton>button {
        border: 1px solid #d4af37;
        background-color: transparent;
        color: #d4af37;
        transition: all 0.3s;
        width: 100%;
    }
    .stButton>button:hover {
        background-color: #d4af37;
        color: #000;
        border: 1px solid #d4af37;
    }
    /* 数据表格美化 */
    .styled-table { border: 1px solid #333; border-radius: 5px; }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 第三部分：核心功能引擎
# ==========================================
class StockMaster:
    @staticmethod
    @st.cache_data(ttl=600)
    def fetch_market_snapshot(threshold):
        """全A股实时快照扫描"""
        df = ak.stock_zh_a_spot_em()
        num_cols = ['今开', '最新价', '最高', '最低', '成交额']
        df[num_cols] = df[num_cols].apply(pd.to_numeric, errors='coerce')
        df = df.dropna(subset=num_cols)
        
        # 形态量化
        df['entity_abs'] = (df['今开'] - df['最新价']).abs()
        df['day_range'] = df['最高'] - df['最低']
        
        # 筛选：阴线 + 十字星比例 + 流动性(成交额>3000万)
        logic = (df['最新价'] < df['今开']) & \
                (df['day_range'] > 0) & \
                (df['entity_abs'] / df['day_range'] <= threshold) & \
                (df['成交额'] > 30000000)
        
        res = df[logic].copy()
        res['形态评分'] = (1 - res['entity_abs'] / res['day_range']) * 100
        return res[['代码', '名称', '最新价', '涨跌幅', '形态评分', '成交额']]

    @staticmethod
    def run_backtest(code, days, threshold):
        """单股回测引擎"""
        df = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq")
        df = df.tail(days + 10).copy()
        df['entity'] = (df['开盘'] - df['收盘']).abs()
        df['range'] = df['最高'] - df['最低']
        df['signal'] = (df['收盘'] < df['开盘']) & (df['range'] > 0) & (df['entity'] / df['range'] <= threshold)
        
        for d in [1, 3, 5]:
            df[f'rev_{d}d'] = (df['收盘'].shift(-d) / df['收盘'] - 1) * 100
        return df

# ==========================================
# 第四部分：App 布局展示
# ==========================================
st.title("妮情 · 深海创意工坊 | 旗舰级选股终端")
st.sidebar.image("https://via.placeholder.com/150x50.png?text=NIQING+STUDIO", use_container_width=True) # 这里可以换成你的Logo链接
st.sidebar.markdown("### 终端控制台")
sens = st.sidebar.slider("十字星灵敏度", 0.05, 0.25, 0.12)
st.sidebar.divider()
st.sidebar.caption("© 2026 NIQING STUDIO. All rights reserved.")

t1, t2 = st.tabs(["🔍 实时扫描", "📊 深度回测"])

with t1:
    if st.button("📡 执行全 A 股云端扫描"):
        with st.spinner("正在解析市场数据..."):
            data = StockMaster.fetch_market_snapshot(sens)
            if not data.empty:
                st.success(f"捕获成功！今日发现 {len(data)} 个高价值信号。")
                st.dataframe(data.sort_values('形态评分', ascending=False), use_container_width=True)
            else:
                st.warning("暂未发现匹配形态，建议调高灵敏度。")

with t2:
    col_l, col_r = st.columns([1, 4])
    with col_l:
        s_code = st.text_input("输入代码", "600519")
        s_days = st.number_input("回顾周期", 200)
    
    if s_code:
        h_data = StockMaster.run_backtest(s_code, s_days, sens)
        sigs = h_data[h_data['signal']]
        
        st.subheader("📈 策略胜率看板")
        m_cols = st.columns(3)
        for i, d in enumerate([1, 3, 5]):
            v = sigs[f'rev_{d}d'].dropna()
            if not v.empty:
                wr = (v > 0).sum() / len(v) * 100
                m_cols[i].metric(f"{d}日持有胜率", f"{wr:.1f}%", f"{v.mean():.2f}% 平均收益")

        fig = go.Figure(data=[go.Candlestick(x=h_data['日期'], open=h_data['开盘'], high=h_data['最高'], low=h_data['最低'], close=h_data['收盘'], name="K线")])
        fig.add_trace(go.Scatter(x=sigs['日期'], y=sigs['最高']*1.03, mode='markers', marker=dict(symbol='diamond', color='#d4af37', size=10), name="变盘信号"))
        fig.update_layout(template="plotly_dark", height=600, margin=dict(t=0,b=0,l=0,r=0))
        st.plotly_chart(fig, use_container_width=True)
