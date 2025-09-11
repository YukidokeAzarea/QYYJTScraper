"""
企研通城投债募集说明书爬虫主程序
支持批量处理、防休眠、反爬虫机制
"""

import os
import sys
import time
import random
import json
import pandas as pd
import ctypes
from pathlib import Path
from typing import List, Dict, Optional
from loguru import logger
from tqdm import tqdm

# 添加src目录到Python路径
sys.path.append(str(Path(__file__).parent))

from .scraper import QYYJTScraper
from .database import DatabaseManager
from .smart_pool import SmartAccountPool
from .config import *


class ProductionScraper:
    """生产环境爬虫主类"""
    
    def __init__(self):
        self.smart_pool = SmartAccountPool()  # 使用智能账号池
        self.db = DatabaseManager()
        self.db.connect()  # 连接数据库
        self.processed_count = 0
        self.error_count = 0
        self.start_time = None
        self.error_log = []  # 错误日志
        self.processed_bonds = set()  # 已处理的债券集合
        self.progress_file = "data/progress.json"
        self.error_file = "data/error_log.json"
        self.resume_file = "data/pause.flag"
        
    def prevent_sleep(self):
        """防止电脑休眠"""
        try:
            # Windows系统防止休眠
            if os.name == 'nt':
                ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)
                logger.info("✅ 已启用防休眠模式")
            else:
                # Linux/Mac系统
                logger.info("⚠️ 非Windows系统，请手动设置防止休眠")
        except Exception as e:
            logger.warning(f"⚠️ 防休眠设置失败: {e}")
    
    def restore_sleep(self):
        """恢复电脑休眠"""
        try:
            if os.name == 'nt':
                ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
                logger.info("✅ 已恢复休眠模式")
        except Exception as e:
            logger.warning(f"⚠️ 恢复休眠设置失败: {e}")
    
    def random_delay(self, min_delay: float = 2.0, max_delay: float = 4.0):
        """随机延迟，防止反爬虫"""
        delay = random.uniform(min_delay, max_delay)
        logger.debug(f"⏳ 随机延迟 {delay:.2f} 秒")
        time.sleep(delay)
    
    def load_bonds_list(self) -> List[Dict]:
        """加载债券列表"""
        try:
            logger.info(f"📖 正在加载债券列表: {BONDS_LIST_PATH}")
            df = pd.read_excel(BONDS_LIST_PATH)
            
            # 检查必要的列
            if '债券简称' not in df.columns:
                raise ValueError("Excel文件中缺少'债券简称'列")
            
            # 过滤掉空值
            df = df.dropna(subset=['债券简称'])
            
            bonds = []
            for _, row in df.iterrows():
                bond_info = {
                    'bond_short_name': str(row['债券简称']).strip(),
                    'bond_code': str(row.get('代码', '')).strip() if pd.notna(row.get('代码')) else '',
                    'issuer': str(row.get('发行人', '')).strip() if pd.notna(row.get('发行人')) else '',
                    'bond_type': str(row.get('债券类型', '')).strip() if pd.notna(row.get('债券类型')) else '',
                    'province': str(row.get('发行人省份', '')).strip() if pd.notna(row.get('发行人省份')) else '',
                    'city': str(row.get('发行人城市', '')).strip() if pd.notna(row.get('发行人城市')) else '',
                }
                bonds.append(bond_info)
            
            logger.info(f"✅ 成功加载 {len(bonds)} 个债券")
            return bonds
            
        except Exception as e:
            logger.error(f"❌ 加载债券列表失败: {e}")
            return []
    
    def process_single_bond(self, bond_info: Dict, progress_bar: tqdm) -> bool:
        """处理单个债券"""
        bond_name = bond_info['bond_short_name']
        
        try:
            logger.info(f"🔍 正在处理债券: {bond_name}")
            
            # 随机延迟
            self.random_delay()
            
            # 使用智能账号池处理债券
            success, result = self.smart_pool.process_bond_with_retry(bond_name)
            if not success:
                error_msg = f"智能账号池处理失败: {bond_name}"
                logger.warning(f"⚠️ {error_msg}")
                self._log_error(bond_name, error_msg, "SMART_POOL_FAILED")
                return False
            
            # 获取解析的文档
            documents = result.get('documents', [])
            if not documents:
                error_msg = f"未找到相关文档: {bond_name}"
                logger.warning(f"⚠️ {error_msg}")
                self._log_error(bond_name, error_msg, "NO_DOCUMENTS")
                return False
            
            # 保存到数据库
            success_count = 0
            for doc in documents:
                try:
                    # 添加额外的债券信息到文档数据（不覆盖API解析的信息）
                    doc.update({
                        'province': bond_info.get('province', ''),
                        'city': bond_info.get('city', ''),
                    })
                    
                    # 插入数据库
                    success = self.db.insert_document(doc)
                    if success:
                        success_count += 1
                        logger.debug(f"✅ 保存文档: {doc.get('document_title', 'Unknown')}")
                    
                except Exception as e:
                    error_msg = f"保存文档失败: {doc.get('document_title', 'Unknown')} - {str(e)}"
                    logger.error(f"❌ {error_msg}")
                    self._log_error(bond_name, error_msg, "SAVE_FAILED", doc.get('document_title', ''))
                    continue
            
            if success_count > 0:
                logger.info(f"✅ 成功处理债券 {bond_name}: {success_count} 个文档")
                self.processed_count += 1
                self.processed_bonds.add(bond_name)
                return True
            else:
                error_msg = f"债券 {bond_name} 没有成功保存任何文档"
                logger.warning(f"⚠️ {error_msg}")
                self._log_error(bond_name, error_msg, "NO_SUCCESSFUL_SAVES")
                return False
                
        except Exception as e:
            error_msg = f"处理债券 {bond_name} 失败: {str(e)}"
            logger.error(f"❌ {error_msg}")
            self._log_error(bond_name, error_msg, "PROCESSING_ERROR")
            self.error_count += 1
            return False
        finally:
            progress_bar.update(1)
    
    def _log_error(self, bond_name: str, error_msg: str, error_type: str, document_title: str = ""):
        """记录错误到日志"""
        error_entry = {
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'bond_name': bond_name,
            'error_type': error_type,
            'error_message': error_msg,
            'document_title': document_title
        }
        self.error_log.append(error_entry)
        
        # 每100个错误保存一次
        if len(self.error_log) % 100 == 0:
            self._save_error_log()
    
    def _save_error_log(self):
        """保存错误日志到文件"""
        try:
            os.makedirs(os.path.dirname(self.error_file), exist_ok=True)
            with open(self.error_file, 'w', encoding='utf-8') as f:
                json.dump(self.error_log, f, ensure_ascii=False, indent=2)
            logger.debug(f"💾 错误日志已保存: {self.error_file}")
        except Exception as e:
            logger.warning(f"⚠️ 保存错误日志失败: {e}")
    
    def _load_progress(self) -> Dict:
        """加载进度文件"""
        try:
            if os.path.exists(self.progress_file):
                with open(self.progress_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"⚠️ 加载进度文件失败: {e}")
        return {}
    
    def _save_progress(self, current: int, total: int):
        """保存进度到文件"""
        try:
            os.makedirs(os.path.dirname(self.progress_file), exist_ok=True)
            progress_data = {
                'current': current,
                'total': total,
                'processed_count': self.processed_count,
                'error_count': self.error_count,
                'processed_bonds': list(self.processed_bonds),
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                'start_time': self.start_time
            }
            
            with open(self.progress_file, 'w', encoding='utf-8') as f:
                json.dump(progress_data, f, ensure_ascii=False, indent=2)
            
            logger.debug(f"💾 进度已保存: {self.progress_file}")
        except Exception as e:
            logger.warning(f"⚠️ 保存进度失败: {e}")
    
    def _create_pause_file(self):
        """创建暂停文件"""
        try:
            os.makedirs(os.path.dirname(self.resume_file), exist_ok=True)
            with open(self.resume_file, 'w') as f:
                f.write(time.strftime('%Y-%m-%d %H:%M:%S'))
            logger.info(f"⏸️ 暂停文件已创建: {self.resume_file}")
        except Exception as e:
            logger.warning(f"⚠️ 创建暂停文件失败: {e}")
    
    def _remove_pause_file(self):
        """删除暂停文件"""
        try:
            if os.path.exists(self.resume_file):
                os.remove(self.resume_file)
                logger.info(f"✅ 暂停文件已删除: {self.resume_file}")
        except Exception as e:
            logger.warning(f"⚠️ 删除暂停文件失败: {e}")
    
    def run_batch_processing(self, start_index: int = 0, max_bonds: Optional[int] = None, 
                           resume_from_file: str = None, resume: bool = False, force: bool = False):
        """批量处理债券"""
        try:
            # 防止休眠
            self.prevent_sleep()
            
            # 加载债券列表
            bonds = self.load_bonds_list()
            if not bonds:
                logger.error("❌ 没有可处理的债券")
                return
            
            # 断点续传逻辑
            if resume:
                progress_data = self._load_progress()
                if progress_data:
                    start_index = progress_data.get('current', 0)
                    self.processed_count = progress_data.get('processed_count', 0)
                    self.error_count = progress_data.get('error_count', 0)
                    self.processed_bonds = set(progress_data.get('processed_bonds', []))
                    
                    # 检查是否已完成所有债券（使用原始债券列表长度）
                    if start_index >= len(bonds):
                        logger.info("✅ 所有债券都已处理完成")
                        return
                    
                    logger.info(f"🔄 断点续传：从第 {start_index + 1} 个债券开始")
                    logger.info(f"📊 已处理: {self.processed_count} 个，错误: {self.error_count} 个")
                    
                    # 应用断点续传的索引调整
                    bonds = bonds[start_index:]
                    logger.info(f"📊 从第 {start_index + 1} 个债券开始处理")
            
            # 检查数据库中已存在的债券，避免重复爬取
            if not force:
                logger.info("🔍 检查数据库中已存在的债券...")
                existing_bonds = self.db.get_existing_bond_short_names()
                if existing_bonds:
                    original_count = len(bonds)
                    bonds = [bond for bond in bonds if bond['bond_short_name'] not in existing_bonds]
                    filtered_count = original_count - len(bonds)
                    logger.info(f"💾 数据库中已存在 {len(existing_bonds)} 个债券的数据")
                    logger.info(f"⏭️ 跳过已爬取的 {filtered_count} 个债券，节省API请求次数")
                    
                    # 显示已存在债券的文档统计
                    if filtered_count > 0:
                        logger.info("📊 已存在债券的文档统计（前10个）：")
                        count = 0
                        for bond in existing_bonds:
                            if count >= 10:
                                break
                            doc_count = self.db.get_bond_document_count(bond)
                            logger.info(f"  - {bond}: {doc_count} 个文档")
                            count += 1
                        if len(existing_bonds) > 10:
                            logger.info(f"  ... 还有 {len(existing_bonds) - 10} 个债券")
            else:
                logger.warning("⚠️ 强制模式：将重新爬取所有债券（包括已存在的）")
                existing_bonds = self.db.get_existing_bond_short_names()
                if existing_bonds:
                    logger.info(f"💾 数据库中已存在 {len(existing_bonds)} 个债券的数据，但将重新爬取")
            
            if max_bonds:
                bonds = bonds[:max_bonds]
                logger.info(f"📊 限制处理 {max_bonds} 个债券")
            
            # 过滤已处理的债券（断点续传）
            # 注意：这里不需要再次过滤，因为已经在上面通过数据库检查过滤过了
            # if resume and self.processed_bonds:
            #     original_count = len(bonds)
            #     bonds = [bond for bond in bonds if bond['bond_short_name'] not in self.processed_bonds]
            #     filtered_count = original_count - len(bonds)
            #     if filtered_count > 0:
            #         logger.info(f"⏭️ 跳过断点续传中已处理的 {filtered_count} 个债券")
            
            total_bonds = len(bonds)
            if total_bonds == 0:
                logger.info("✅ 所有债券都已处理完成")
                return
            
            logger.info(f"🚀 开始批量处理 {total_bonds} 个债券")
            
            # 初始化智能账号池
            logger.info("🔐 正在初始化智能账号池...")
            if not self.smart_pool.initialize():
                logger.error("❌ 智能账号池初始化失败，无法继续处理")
                return
            logger.info("✅ 智能账号池初始化成功！")
            
            # 记录开始时间
            self.start_time = time.time()
            
            # 创建进度条
            progress_bar = tqdm(
                total=total_bonds,
                desc="处理债券",
                unit="个",
                ncols=100,
                colour='green'
            )
            
            # 处理每个债券
            for i, bond_info in enumerate(bonds):
                try:
                    # 检查是否需要暂停
                    if resume_from_file and os.path.exists(resume_from_file):
                        logger.info("⏸️ 检测到暂停文件，停止处理")
                        self._create_pause_file()
                        break
                    
                    # 处理单个债券
                    success = self.process_single_bond(bond_info, progress_bar)
                    
                    # 每处理50个债券显示一次统计
                    if (i + 1) % 50 == 0:
                        self._show_progress_stats(i + 1, total_bonds)
                    
                    # 每处理100个债券保存一次进度
                    if (i + 1) % 100 == 0:
                        self._save_progress(start_index + i + 1, start_index + total_bonds)
                    
                except KeyboardInterrupt:
                    logger.info("⏸️ 用户中断处理")
                    self._create_pause_file()
                    break
                except Exception as e:
                    error_msg = f"处理过程中发生错误: {str(e)}"
                    logger.error(f"❌ {error_msg}")
                    self._log_error(bond_info['bond_short_name'], error_msg, "BATCH_ERROR")
                    self.error_count += 1
                    continue
            
            # 关闭进度条
            progress_bar.close()
            
            # 保存最终进度和错误日志
            self._save_progress(start_index + total_bonds, start_index + total_bonds)
            self._save_error_log()
            
            # 删除暂停文件（如果存在）
            self._remove_pause_file()
            
            # 显示最终统计
            self._show_final_stats()
            
        except Exception as e:
            logger.error(f"❌ 批量处理失败: {e}")
            self._create_pause_file()
        finally:
            # 恢复休眠
            self.restore_sleep()
            # 关闭资源
            self.cleanup()
    
    def _show_progress_stats(self, current: int, total: int):
        """显示进度统计"""
        elapsed = time.time() - self.start_time
        rate = current / elapsed if elapsed > 0 else 0
        eta = (total - current) / rate if rate > 0 else 0
        
        logger.info(f"📊 进度统计: {current}/{total} ({current/total*100:.1f}%) | "
                   f"成功: {self.processed_count} | 错误: {self.error_count} | "
                   f"速度: {rate:.1f}个/秒 | 预计剩余: {eta/60:.1f}分钟")
    
    
    def _show_final_stats(self):
        """显示最终统计"""
        if self.start_time:
            elapsed = time.time() - self.start_time
            rate = self.processed_count / elapsed if elapsed > 0 else 0
            
            logger.info("=" * 60)
            logger.info("🎉 批量处理完成！")
            logger.info(f"📊 总处理时间: {elapsed/3600:.2f} 小时")
            logger.info(f"✅ 成功处理: {self.processed_count} 个债券")
            logger.info(f"❌ 处理失败: {self.error_count} 个债券")
            logger.info(f"⚡ 平均速度: {rate:.2f} 个债券/秒")
            logger.info("=" * 60)
    
    def cleanup(self):
        """清理资源"""
        try:
            if self.smart_pool:
                self.smart_pool.cleanup()
            if self.db:
                self.db.close()
            logger.info("🧹 资源清理完成")
        except Exception as e:
            logger.warning(f"⚠️ 资源清理失败: {e}")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='企研通城投债募集说明书爬虫')
    parser.add_argument('--start', type=int, default=0, help='开始处理的债券索引')
    parser.add_argument('--max', type=int, help='最大处理数量')
    parser.add_argument('--resume', action='store_true', help='断点续传模式')
    parser.add_argument('--pause', type=str, help='暂停文件路径')
    parser.add_argument('--test', action='store_true', help='测试模式（只处理1个债券）')
    parser.add_argument('--force', action='store_true', help='强制重新爬取所有债券（包括已存在的）')
    
    args = parser.parse_args()
    
    # 测试模式
    if args.test:
        args.max = 1
        logger.info("🧪 测试模式：只处理1个债券")
    
    # 创建生产爬虫实例
    scraper = ProductionScraper()
    
    try:
        # 开始批量处理
        scraper.run_batch_processing(
            start_index=args.start,
            max_bonds=args.max,
            resume_from_file=args.pause,
            resume=args.resume,
            force=args.force
        )
    except KeyboardInterrupt:
        logger.info("⏸️ 程序被用户中断")
    except Exception as e:
        logger.error(f"❌ 程序运行失败: {e}")
    finally:
        scraper.cleanup()


if __name__ == "__main__":
    main()
