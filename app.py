import streamlit as st
import akshare as ak
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time

# ==========================================
# 1. 界面配置与视觉风格
# ==========================================
st.set_page_config(page_title="NIQING | 全指标旗舰终端", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #0b0e14; color: #e0e0e0; }
    [data-testid="stMetricValue"] { color: #d4af37 !important; font-family: 'Courier New', monospace; }
    .stButton>button { border: 1px solid #d4af37; color: #d4af37; background: transparent; width: 100%; font-weight: bold; }
    .stButton>button:hover { background-color: #d4af37; color: black; }
    .stTabs [data-baseweb="tab-list"] { gap: 24px; }
    .stTabs [data-baseweb="tab"] { height: 50px; white-space: pre-wrap; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. 授权检查
# ==========================================
def check_auth():
    if "auth_ok" not in st.session_state:
        st.markdown("<h2 style='text-align: center; color: #d4af37;'>NIQING STUDIO 策略终端</h2>", unsafe_allow_html=True)
        col_a, col_b, col_c = st.columns([1,2,1])
        with col_b:
            pwd = st.text_input("授权令牌", type="password", placeholder="输入访问密码...")
            if pwd == "niqing888": # 默认密码
                st.session_state.auth_ok = True
                st.rerun()
            elif pwd:
                st.error("令牌无效，请联系 NIQING STUDIO")
        return False
    return True

if not check_auth():
    st.stop()

# ==========================================
# 3. 核心计算引擎 (手动实现指标)
# ==========================================
class StockEngine:
    @staticmethod
    def retry_fetch(func, *args, **kwargs):
        """抗网络波动抓取"""
        for i in range(3):
            try:
                data = func(*args, **kwargs)
                if data is not None and not data.empty: return data
            except:
                time.sleep(1.5)
        return pd.DataFrame()

    @staticmethod
    def calculate_kdj(df, n=9, m1=3, m2=3):
        """手动计算 KDJ (与通达信/东财标准一致)"""
        low_list = df['最低'].rolling(window=n).min()
        high_list = df['最高'].rolling(window=n).max()
        rsv = (df['收盘'] - low_list) / (high_list - low_list) * 100
        df['K'] = rsv.ewm(com=m1-1, adjust=False).mean()
        df['D'] = df['K'].ewm(com=m2-1, adjust=False).mean()
        df['J'] = 3 * df['K'] - 2 * df['D']
        return df

    @classmethod
    @st.cache_data(ttl=600)
    def scan_market(cls, threshold):
        """全A股实时快照筛选"""
        df = cls.retry_fetch(ak.stock_zh_a_spot_em)
        if df.empty: return df
        
        # 清洗数据
        cols = ['今开', '最新价', '最高', '最低', '成交额', '成交量']
        df[cols] = df[cols].apply(pd.to_numeric, errors='coerce')
        df = df.dropna(subset=cols)
        
        # 十字星逻辑
        df['entity'] = (df['今开'] - df['最新价']).abs()
        df['range'] = df['最高'] - df['最低']
        
        mask = (df['最新价'] < df['今开']) & (df['range'] > 0) & \
               (df['entity'] / df['range'] <= threshold) & (df['成交额'] > 20000000)
        
        res = df[mask].copy()
        res['形态评分'] = (1 - res['entity'] / res['range']) * 100
        return res[['代码', '名称', '最新价', '涨跌幅', '形态评分', '成交量', '成交额']]

    @classmethod
    def get_backtest_data(cls, symbol, days, threshold):
        """获取包含 KDJ 和成交量的历史数据"""
        start_date = (pd.Timestamp.now() - pd.Timedelta(days=days+60)).strftime('%Y%m%d')
        df = cls.retry_fetch(ak.stock_zh_a_hist, symbol=symbol, period="daily", start_date=start_date, adjust="qfq")
        
        if df.empty: return df
        
        # 计算全量指标
        df = cls.calculate_kdj(df)
        df['vol_ma5'] = df['成交量'].rolling(5).mean()
        
        # 信号判定
        df['entity'] = (df['开盘'] - df['收盘']).abs()
        df['range'] = df['最高'] - df['最低']
        df['signal'] = (df['收盘'] < df['开盘']) & (df['range'] > 0) & (df['entity'] / df['range'] <= threshold)
        
        # 收益统计
        for d in [1, 3, 5]:
            df[f'ret_{d}d'] = (df['收盘'].shift(-d) / df['收盘'] - 1) * 100
            
        return df

# ==========================================
# 4. 界面展示逻辑
# ==========================================
st.title("妮情 · 全指标深度策略终端")
st.sidebar.header("🕹️ 终端配置")
sens = st.sidebar.slider("十字星灵敏度", 0.05, 0.25, 0.12)
st.sidebar.info("Tips: KDJ 低位(J<20)配合阴线十字星通常是强反转信号。")

tab1, tab2 = st.tabs(["🚀 全速实时扫描", "📊 多维指标回测"])

with tab1:
    if st.button("📡 执行全 A 股深度扫描"):
        with st.spinner("正在同步全球金融数据库..."):
            results = StockEngine.scan_market(sens)
            if not results.empty:
                st.success(f"扫描完成！今日捕获 {len(results)} 个信号")
                st.dataframe(results.sort_values('形态评分', ascending=False), use_container_width=True, height=500)
            else:
                st.warning("暂无匹配，请适当调高灵敏度")

with tab2:
    c1, c2 = st.columns([1, 4])
    with c1:
        s_code = st.text_input("股票代码", "600519")
        s_days = st.number_input("回顾周期", 120)
    
    if s_code:
        with st.spinner("正在解析量化指标..."):
            hist = StockEngine.get_backtest_data(s_code, s_days, sens)
            if not hist.empty:
                sigs = hist[hist['signal']]
                
                # 统计看板
                st.subheader("📊 历史信号统计")
                m_cols = st.columns(3)
                for i, d in enumerate([1, 3, 5]):
                    v = sigs[f'ret_{d}d'].dropna()
                    if not v.empty:
                        wr = (v > 0).sum() / len(v) * 100
                        m_cols[i].metric(f"{d}日胜率", f"{wr:.1f}%", f"{v.mean():.2f}% 平均收益")

                # 绘制三层看板 (K线/成交量/KDJ)
                fig = make_subplots(rows=3, cols=1, shared_xaxes=True, 
                                    vertical_spacing=0.03, row_heights=[0.5, 0.2, 0.3],
                                    subplot_titles=("K线信号", "成交量(VOL)", "KDJ指标"))
                
                # 1. K线
                fig.add_trace(go.Candlestick(x=hist['日期'], open=hist['开盘'], high=hist['最高'], low=hist['最低'], close=hist['收盘'], name="日K"), row=1, col=1)
                fig.add_trace(go.Scatter(x=sigs['日期'], y=sigs['最高']*1.03, mode='markers', marker=dict(symbol='star', size=12, color='#d4af37'), name="信号点"), row=1, col=1)
                
                # 2. 成交量
                v_colors = ['#ff4b4b' if c < o else '#00cc96' for c, o in zip(hist['收盘'], hist['开盘'])]
                fig.add_trace(go.Bar(x=hist['日期'], y=hist['成交量'], marker_color=v_colors, name="成交量"), row=2, col=1)
                fig.add_trace(go.Scatter(x=hist['日期'], y=hist['vol_ma5'], line=dict(color='white', width=1), name="均量"), row=2, col=1)
                
                # 3. KDJ
                fig.add_trace(go.Scatter(x=hist['日期'], y=hist['K'], line=dict(color='#ffffff', width=1.5), name="K"), row=3, col=1)
                fig.add_trace(go.Scatter(x=hist['日期'], y=hist['D'], line=dict(color='#ffff00', width=1.5), name="D"), row=3, col=1)
                fig.add_trace(go.Scatter(x=hist['日期'], y=hist['J'], line=dict(color='#ff00ff', width=1.5), name="J"), row=3, col=1)
                fig.add_hline(y=20, line_dash="dot", line_color="gray", row=3, col=1)
                fig.add_hline(y=80, line_dash="dot", line_color="gray", row=3, col=1)
                
                fig.update_layout(height=800, template="plotly_dark", xaxis_rangeslider_visible=False, margin=dict(t=50, b=50, l=0, r=0))
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.error("数据抓取超时，请重试")
