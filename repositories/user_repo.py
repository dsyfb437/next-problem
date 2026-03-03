"""
用户仓库 - 用户数据访问层
"""
import json
import os
from pathlib import Path
from typing import Optional, List, Dict
from models.user import User


class UserRepository:
    """用户数据仓库"""

    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.index_file = self.data_dir / "users_index.json"

    def _load_index(self) -> Dict:
        """加载用户索引"""
        if self.index_file.exists():
            with open(self.index_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"users": []}

    def _save_index(self, index: Dict):
        """保存用户索引"""
        with open(self.index_file, "w", encoding="utf-8") as f:
            json.dump(index, f, ensure_ascii=False, indent=2)

    def get_by_username(self, username: str) -> Optional[Dict]:
        """根据用户名查找用户信息"""
        index = self._load_index()
        for user_info in index.get("users", []):
            if user_info["username"] == username:
                return user_info
        return None

    def get_by_id(self, user_id: str) -> Optional[Dict]:
        """根据用户ID查找用户信息"""
        index = self._load_index()
        for user_info in index.get("users", []):
            if user_info["user_id"] == user_id:
                return user_info
        return None

    def save(self, user: User) -> None:
        """保存用户数据"""
        file_path = self.data_dir / f"user_{user.user_id}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(user.to_dict(), f, ensure_ascii=False, indent=2)

    def load(self, user_id: str) -> Optional[User]:
        """加载用户数据"""
        file_path = self.data_dir / f"user_{user_id}.json"
        if not file_path.exists():
            return None

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return User.from_dict(data)
        except (json.JSONDecodeError, KeyError):
            # 文件损坏，返回None
            return None

    def create_user(self, username: str, password_hash: str, user_id: str) -> User:
        """创建新用户"""
        from datetime import datetime

        user = User(
            user_id=user_id,
            username=username,
            password_hash=password_hash,
            created_at=datetime.now().isoformat()
        )

        # 添加到索引
        index = self._load_index()
        index["users"].append({
            "username": username,
            "user_id": user_id
        })
        self._save_index(index)

        # 保存用户数据
        self.save(user)
        return user

    def delete(self, user_id: str) -> bool:
        """删除用户"""
        # 从索引中移除
        index = self._load_index()
        original_len = len(index["users"])
        index["users"] = [u for u in index["users"] if u["user_id"] != user_id]
        self._save_index(index)

        if len(index["users"]) < original_len:
            # 删除用户文件
            file_path = self.data_dir / f"user_{user_id}.json"
            if file_path.exists():
                os.remove(file_path)
            return True
        return False
