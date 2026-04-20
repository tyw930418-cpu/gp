import streamlit as st
import akshare as ak
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time
import random

# --- 1. 终端视觉与基础配置 ---
st.set_page_config(page_title="NIQING | 行业金叉雷达", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #0b0e14; color: #e0e0e0; }
    .stHeader { background-color: #1a1c23; }
    .gold-text { color: #d4af37 !important; font-weight: bold; }
    .stButton>button { border: 1px solid #d4af37; color: #d4af37; background: transparent; width: 100%; }
    .stButton>button:hover { background-color: #d4af37; color: black; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 授权验证 ---
if "auth" not in st.session_state:
    st.markdown("<h2 style='text-align: center; color: #d4af37;'>NIQING STUDIO 策略终端</h2>", unsafe_allow_html=True)
    if st.text_input("授权令牌", type="password") == "niqing888":
        st.session_state.auth = True
        st.rerun()
    st.stop()

# --- 3. 核心计算类 (整合 NIQING 引擎) ---
class NIQINGEngine:
    @staticmethod
    def safe_fetch(func, **kwargs):
        """稳健抓取，带重试机制"""
        for _ in range(3):
            try:
                time.sleep(random.uniform(0.3, 0.6))
                return func(**kwargs)
            except:
                time.sleep(1)
        return pd.DataFrame()

    @staticmethod
    def calc_kdj(df):
        """计算 KDJ 指标"""
        if df.empty: return df
        low_9 = df['最低'].rolling(9).min()
        high_9 = df['最高'].rolling(9).max()
        # 避免除以0
        rsv = (df['收盘'] - low_9) / (high_9 - low_9 + 0.001) * 100
        df['K'] = rsv.ewm(com=2, adjust=False).mean()
        df['D'] = df['K'].ewm(com=2, adjust=False).mean()
        df['J'] = 3 * df['K'] - 2 * df['D']
        return df

# --- 4. UI 交互布局 ---
st.title("妮情 · 行业分类与金叉实时预警")

# 侧边栏：行业选择
st.sidebar.markdown("### 📂 市场筛选")
# 你可以在这里自行添加更多行业名称
industry_list = ["半导体", "通信设备", "电力行业", "汽车整车", "酿酒行业", "生物制品", "软件开发", "光伏设备", "房地产", "银行"]
selected_industry = st.sidebar.selectbox("1. 选择目标行业", industry_list)

# 主界面分为左右两栏
col_list, col_chart = st.columns([1, 2.5])

with col_list:
    st.markdown(f"#### 📍 {selected_industry} 板块")
    
    # 行业同步按钮
    if st.button("🔄 同步行业成员数据"):
        with st.spinner("获取中..."):
            df_ind = NIQINGEngine.safe_fetch(ak.stock_board_industry_cons_em, symbol=selected_industry)
            if not df_ind.empty:
                st.session_state.ind_data = df_ind[['代码', '名称', '最新价', '涨跌幅']]
                st.success("同步成功")
            else:
                st.error("无法获取行业数据，请稍后重试")

    # 股票选择器
    if "ind_data" in st.session_state:
        stock_options = st.session_state.ind_data['名称'].tolist()
        selected_stock_name = st.selectbox("2. 选择个股进行检测", stock_options)
        
        # 获取对应代码
        target_code = st.session_state.ind_data[st.session_state.ind_data['名称'] == selected_stock_name]['代码'].values[0]
        
        # 显示选中的股票快照数据
        row = st.session_state.ind_data[st.session_state.ind_data['名称'] == selected_stock_name].iloc[0]
        st.metric("实时价", f"¥{row['最新价']}", f"{row['涨跌幅']}%")
    else:
        st.info("请先点击上方按钮同步行业成员")
        target_code = None

with col_chart:
    if target_code:
        st.markdown(f"#### 📊 {selected_stock_name} ({target_code}) 深度扫描")
        
        # 抓取历史数据并分析
        with st.spinner("正在加载技术面数据..."):
            h_df = NIQINGEngine.safe_fetch(ak.stock_zh_a_hist, symbol=target_code, adjust="qfq")
            
            if not h_df.empty:
                h_df = NIQINGEngine.calc_kdj(h_df)
                
                # --- 金叉检测核心逻辑 ---
                last = h_df.iloc[-1]
                prev = h_df.iloc[-2]
                # 金叉定义：昨日K < D，今日K > D
                is_golden = (prev['K'] < prev['D']) and (last['K'] > last['D'])
                
                if is_golden:
                    # 界面顶部显眼的大屏横幅提示
                    st.markdown(f"""
                        <div style="padding:20px; background-color:rgba(46, 204, 113, 0.2); border:2px solid #2ecc71; border-radius:10px; text-align:center; margin-bottom:20px;">
                            <h2 style="color:#2ecc71; margin:0;">🔥 金叉预警：{selected_stock_name} 触发！</h2>
                            <p style="margin:5px 0 0 0; color:#e0e0e0;">该股今日 KDJ 指标达成多头金叉形态</p>
                        </div>
                    """, unsafe_allow_html=True)
                    st.toast(f"{selected_stock_name} 触发金叉！", icon="⭐")
                else:
                    st.markdown("""
                        <div style="padding:20px; background-color:rgba(149, 165, 166, 0.1); border:1px solid #7f8c8d; border-radius:10px; text-align:center; margin-bottom:20px;">
                            <h3 style="color:#bdc3c7; margin:0;">指标平稳</h3>
                            <p style="margin:5px 0 0 0;">目前未检测到 KDJ 金叉交叉点</p>
                        </div>
                    """, unsafe_allow_html=True)

                # 绘制专业三层图表
                fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.05)
                
                # K线图
                fig.add_trace(go.Candlestick(
                    x=h_df['日期'], open=h_df['开盘'], high=h_df['最高'], 
                    low=h_df['最低'], close=h_df['收盘'], name="K线"
                ), row=1, col=1)
                
                # KDJ 指标曲线
                fig.add_trace(go.Scatter(x=h_df['日期'], y=h_df['K'], line=dict(color='white', width=1), name="K"), row=2, col=1)
                fig.add_trace(go.Scatter(x=h_df['日期'], y=h_df['D'], line=dict(color='yellow', width=1), name="D"), row=2, col=1)
                fig.add_trace(go.Scatter(x=h_df['日期'], y=h_df['J'], line=dict(color='purple', width=1.5), name="J"), row=2, col=1)
                
                # 装饰性参考线
                fig.add_hline(y=20, line_dash="dot", line_color="rgba(255,255,255,0.2)", row=2, col=1)
                fig.add_hline(y=80, line_dash="dot", line_color="rgba(255,255,255,0.2)", row=2, col=1)

                fig.update_layout(height=650, template="plotly_dark", xaxis_rangeslider_visible=False, margin=dict(t=30, b=30))
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.error("数据源抓取超时，请稍后再次点击选择股票。")
