"""
test_signature.py - QQ Bot Webhook Ed25519 签名验证测试用例

基于 test.txt 中的 Go 示例代码翻译为 Python，用于验证 Ed25519 签名生成是否正确。
"""

import unittest
import hashlib


# ── Ed25519 签名实现（与 Go 示例等价）──

def derive_ed25519_seed(secret: str) -> bytes:
    """从 bot secret 派生出 32 字节的 Ed25519 种子。

    算法与 Go 示例完全一致：
    1. 重复 secret 直到长度 >= 32
    2. 截取前 32 字节
    """
    seed = secret
    while len(seed) < 32:
        seed = seed * 2  # Go 的 strings.Repeat(seed, 2) 等价于 Python 的 seed * 2
    return seed[:32].encode("utf-8")


def compute_ed25519_signature(secret: str, event_ts: str, plain_token: str) -> str:
    """使用 Ed25519 计算 QQ Bot Webhook 验证签名。

    Args:
        secret:      机器人密钥
        event_ts:    事件时间戳（来自请求 body 的 d.event_ts）
        plain_token: 明文 token（来自请求 body 的 d.plain_token）

    Returns:
        64 位十六进制签名字符串
    """
    import nacl.signing

    seed = derive_ed25519_seed(secret)
    # 从种子生成签名密钥
    signing_key = nacl.signing.SigningKey(seed)
    # 签名内容 = event_ts + plain_token（字符串拼接）
    message = (event_ts + plain_token).encode("utf-8")
    # Ed25519 签名
    signed = signing_key.sign(message)
    # 提取 64 字节的签名部分（不含原始消息）
    signature_bytes = signed.signature
    return signature_bytes.hex()


# ══════════════════════════════════════════════════════════════════════
# 单元测试
# ══════════════════════════════════════════════════════════════════════

class TestEd25519Signature(unittest.TestCase):
    """QQ Bot Webhook Ed25519 签名测试"""

    def test_derive_seed_from_short_secret(self):
        """测试：短密钥衍生 32 字节种子"""
        secret = "DG5g3B4j9X2KOErG"  # 16 字符
        seed = derive_ed25519_seed(secret)
        self.assertEqual(len(seed), 32, "种子必须是 32 字节")
        # 16 * 2 = 32，刚好一次翻倍即满足
        expected = (secret * 2)[:32].encode("utf-8")
        self.assertEqual(seed, expected, "种子值不匹配")

    def test_derive_seed_from_longer_secret(self):
        """测试：长密钥衍生种子"""
        secret = "abcdefghijklmnopqrstuvwxyz012345"  # 32 字符
        seed = derive_ed25519_seed(secret)
        self.assertEqual(len(seed), 32)
        self.assertEqual(seed, secret[:32].encode("utf-8"))

    def test_derive_seed_from_very_short_secret(self):
        """测试：超短密钥需多次翻倍"""
        secret = "abc"  # 3 字符
        seed = derive_ed25519_seed(secret)
        self.assertEqual(len(seed), 32)
        # 3 -> 6 -> 12 -> 24 -> 48 -> truncate to 32
        expected = "abcabcabcabcabcabcabcabcabcabcab"  # "abc"*10 + "ab" = 32
        self.assertEqual(seed.decode("utf-8"), expected)

    def test_signature_matches_expected(self):
        """核心测试：签名结果与 Go 示例一致。

        test.txt 中提供的正确返回值：
          signature = 87befc99c42c651b...
        使用同样的参数必须得到同样的签名。
        """
        secret = "DG5g3B4j9X2KOErG"
        plain_token = "Arq0D5A61EgUu4OxUvOp"
        event_ts = "1725442341"

        expected_signature = (
            "87befc99c42c651b3aac0278e71ada338433ae26fcb24307bdc5ad38c1adc2d0"
            "1bcfcadc0842edac85e85205028a1132afe09280305f13aa6909ffc2d652c706"
        )

        result = compute_ed25519_signature(secret, event_ts, plain_token)
        self.assertEqual(
            result, expected_signature,
            f"\n期望签名: {expected_signature}\n实际签名: {result}\n签名不匹配！"
        )

    def test_signature_different_params_produce_different_results(self):
        """测试：不同参数产生不同签名"""
        secret = "DG5g3B4j9X2KOErG"
        sig1 = compute_ed25519_signature(secret, "1725442341", "tokenA")
        sig2 = compute_ed25519_signature(secret, "1725442341", "tokenB")
        self.assertNotEqual(sig1, sig2, "不同 plain_token 应产生不同签名")

        sig3 = compute_ed25519_signature(secret, "1725442342", "tokenA")
        self.assertNotEqual(sig1, sig3, "不同 event_ts 应产生不同签名")

        secret2 = "DifferentSecret12"
        sig4 = compute_ed25519_signature(secret2, "1725442341", "tokenA")
        self.assertNotEqual(sig1, sig4, "不同 secret 应产生不同签名")

    def test_hmac_does_not_match(self):
        """对比测试：HMAC-SHA256 算法不会产生正确的签名。

        证明当前的 HMAC 实现是错误的，返回值与 QQ 平台预期不符。
        """
        import hmac

        secret = "DG5g3B4j9X2KOErG"
        plain_token = "Arq0D5A61EgUu4OxUvOp"

        expected_signature = (
            "87befc99c42c651b3aac0278e71ada338433ae26fcb24307bdc5ad38c1adc2d0"
            "1bcfcadc0842edac85e85205028a1132afe09280305f13aa6909ffc2d652c706"
        )

        # 当前 bot.py 的错误实现
        hmac_sig = hmac.new(
            secret.encode("utf-8"),
            plain_token.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        self.assertNotEqual(
            hmac_sig, expected_signature,
            "HMAC 不应产生正确的 Ed25519 签名，这就是签名验证失败的原因！",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
