"""
小红书矩阵内容赛马与数据洞察大屏 — Streamlit 前端（云端专属版）
仅保留数据赛马大屏，纯 Supabase 数据源，无本地依赖。
"""

import streamlit as st
import pandas as pd

from supabase import create_client

# ============================================================
#   Supabase 云端凭证（硬编码）
# ============================================================
SUPABASE_URL = "https://dtpqcmuchzpysozfftrs.supabase.co"
SUPABASE_KEY = "sb_publishable_DtvjWjosXH_xFl7bZAiygQ_XzL8znua"
TABLE_NAME   = "xhs_data"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ============================================================
#   数据读取层（Supabase + Streamlit 缓存）
# ============================================================

@st.cache_data(ttl=600)
def load_notes() -> pd.DataFrame:
    """从 Supabase xhs_data 表读取全量笔记"""
    resp = supabase.table(TABLE_NAME).select("*").execute()
    if resp.data:
        return pd.DataFrame(resp.data)
    return pd.DataFrame()


# ============================================================
#   基于 DataFrame 的聚合查询
# ============================================================

def get_stats(df: pd.DataFrame) -> dict:
    """核心统计指标（账号数由笔记中的 account_name 去重得出）"""
    return {
        "account_count":     int(df["account_name"].nunique()) if not df.empty else 0,
        "note_count":        len(df),
        "max_likes":         int(df["likes"].max()) if not df.empty else 0,
        "total_comments":    int(df["comments"].sum()) if not df.empty else 0,
        "total_collections": int(df["collections"].sum()) if not df.empty else 0,
    }


def get_all_themes(df: pd.DataFrame) -> list:
    """所有主题（去重排序）"""
    if df.empty:
        return []
    return sorted(df["theme"].dropna().unique().tolist())


def get_theme_data(df: pd.DataFrame, theme: str, metric: str = "likes") -> list:
    """按主题、账号聚合指定度量"""
    valid = {"likes", "comments", "collections"}
    if metric not in valid:
        metric = "likes"
    filtered = df[df["theme"] == theme]
    if filtered.empty:
        return []
    grouped = (
        filtered.groupby("account_name")[metric]
        .sum()
        .reset_index()
        .sort_values(metric, ascending=False)
    )
    grouped.columns = ["account_name", f"total_{metric}"]
    return grouped.to_dict("records")


def get_notes_by_theme(df: pd.DataFrame, theme: str) -> list:
    """按主题返回笔记详情，按点赞降序"""
    filtered = df[df["theme"] == theme]
    if filtered.empty:
        return []
    filtered = filtered.sort_values("likes", ascending=False)
    cols = ["account_name", "title", "theme", "likes", "comments",
            "collections", "publish_date", "link"]
    available = [c for c in cols if c in filtered.columns]
    return filtered[available].to_dict("records")


# ============================================================
#   Streamlit 页面配置
# ============================================================

st.set_page_config(
    page_title="小红书矩阵赛马大屏",
    page_icon="📊",
    layout="wide",
)

st.markdown(
    """
<style>
    #MainMenu, footer, header {visibility: hidden;}
    [data-testid="stMetricValue"] {font-size: 1.6rem !important;}
    .main-title {
        font-size: 1.8rem; font-weight: 700;
        background: linear-gradient(135deg, #FF5A5F, #E94057);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    }
</style>
""",
    unsafe_allow_html=True,
)

# ============================================================
#   📈 数据赛马大屏（唯一页面）
# ============================================================

st.markdown(
    '<p class="main-title">🏇 小红书矩阵内容赛马大屏</p>',
    unsafe_allow_html=True,
)
st.markdown("---")

col_refresh, *_ = st.columns([1, 6])
if col_refresh.button("🔄 刷新数据"):
    st.cache_data.clear()
    st.rerun()

# ── 加载云端数据 ──
df_notes = load_notes()
stats    = get_stats(df_notes)

# ── 五大核心指标卡片 ──
c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    st.metric("📋 监控账号数", stats["account_count"])
with c2:
    st.metric("📝 已收录笔记数", stats["note_count"])
with c3:
    st.metric("🔥 全盘最高点赞", stats["max_likes"])
with c4:
    st.metric("💬 全盘总评论数", stats["total_comments"])
with c5:
    st.metric("⭐ 全盘总收藏数", stats["total_collections"])

st.markdown("---")

themes = get_all_themes(df_notes)
if not themes:
    st.info("暂无笔记数据，等待云端同步。")
else:
    # ── 跨号主题赛马图 ──
    st.subheader("🎯 跨号主题赛马图")

    col_theme, col_metric = st.columns([1, 1])
    with col_theme:
        selected_theme = st.selectbox("选择主题类型", themes, key="theme_select")
    with col_metric:
        metric_label_map = {
            "likes":       "👍 点赞数",
            "comments":    "💬 评论数",
            "collections": "⭐ 收藏数",
        }
        selected_metric_key = st.selectbox(
            "选择度量指标",
            list(metric_label_map.keys()),
            format_func=lambda k: metric_label_map[k],
            key="metric_select",
        )

    theme_stats = get_theme_data(df_notes, selected_theme, metric=selected_metric_key)
    metric_col = f"total_{selected_metric_key}"
    metric_label = metric_label_map[selected_metric_key]

    if theme_stats:
        df_bar = pd.DataFrame(theme_stats)
        df_bar = df_bar.rename(
            columns={"account_name": "账号名称", metric_col: metric_label}
        )
        df_bar = df_bar.set_index("账号名称")
        st.bar_chart(df_bar, use_container_width=True)
    else:
        st.warning(f"主题「{selected_theme}」暂无数据。")

    st.markdown("---")

    # ── 笔记透视表 ──
    st.subheader("📋 笔记透视表")
    notes = get_notes_by_theme(df_notes, selected_theme)
    if notes:
        df_notes_view = pd.DataFrame(notes)
        df_notes_view = df_notes_view.rename(
            columns={
                "account_name": "账号",
                "title":        "标题",
                "theme":        "主题",
                "likes":        "点赞数",
                "comments":     "评论数",
                "collections":  "收藏数",
                "publish_date": "发布日期",
                "link":         "链接",
            }
        )
        column_order = [
            "账号", "标题", "主题", "发布日期",
            "点赞数", "评论数", "收藏数", "链接",
        ]
        df_notes_view = df_notes_view[[c for c in column_order if c in df_notes_view.columns]]

        st.dataframe(
            df_notes_view,
            use_container_width=True,
            hide_index=True,
            column_config={
                "点赞数":  st.column_config.NumberColumn("点赞数", format="%d"),
                "评论数":  st.column_config.NumberColumn("评论数", format="%d"),
                "收藏数":  st.column_config.NumberColumn("收藏数", format="%d"),
                "链接":    st.column_config.LinkColumn("链接"),
            },
        )
    else:
        st.info("暂无数据，等待同步。")
