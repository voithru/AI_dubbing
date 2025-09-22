"""
토큰 사용량 및 비용 추적 모듈
LLM API 호출 시 토큰 사용량을 추적하고 비용을 계산합니다.
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict


@dataclass
class TokenUsage:
    """토큰 사용량 정보"""
    input_tokens: int
    output_tokens: int
    total_tokens: int
    model: str
    timestamp: str
    text_length: int
    audio_duration: Optional[float] = None


@dataclass
class CostInfo:
    """비용 정보"""
    input_cost: float
    output_cost: float
    total_cost: float
    currency: str = "USD"


class TokenTracker:
    """토큰 사용량 및 비용 추적기"""
    
    # Gemini API 가격표 (2024년 기준, 실제 가격은 Google AI Studio에서 확인 필요)
    GEMINI_PRICING = {
        "gemini-2.5-pro-preview-tts": {
            "input_tokens_per_1m": 1.00,   # $1.00 per 1M input tokens
            "output_tokens_per_1m": 20.00,  # $20.00 per 1M output tokens
        }
    }
    
    def __init__(self, output_dir: str = "output"):
        """
        토큰 추적기를 초기화합니다.
        
        Args:
            output_dir (str): 비용 보고서를 저장할 디렉토리
        """
        self.output_dir = output_dir
        self.video_costs: Dict[str, List[TokenUsage]] = {}
        self.session_start = datetime.now().isoformat()
        
        # 출력 디렉토리 생성
        os.makedirs(output_dir, exist_ok=True)
    
    def add_token_usage(
        self,
        video_name: str,
        input_tokens: int,
        output_tokens: int,
        model: str,
        text_length: int,
        audio_duration: Optional[float] = None
    ):
        """
        토큰 사용량을 추가합니다.
        
        Args:
            video_name (str): 영상 이름
            input_tokens (int): 입력 토큰 수
            output_tokens (int): 출력 토큰 수 (오디오의 경우 추정값)
            model (str): 사용된 모델명
            text_length (int): 입력 텍스트 길이
            audio_duration (float, optional): 생성된 오디오 길이 (초)
        """
        usage = TokenUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            model=model,
            timestamp=datetime.now().isoformat(),
            text_length=text_length,
            audio_duration=audio_duration
        )
        
        if video_name not in self.video_costs:
            self.video_costs[video_name] = []
        
        self.video_costs[video_name].append(usage)
        
        print(f"📊 토큰 사용량 추가 - {video_name}: {input_tokens} 입력 + {output_tokens} 출력 = {usage.total_tokens} 토큰")
    
    def calculate_cost(self, usage: TokenUsage) -> CostInfo:
        """
        토큰 사용량을 기반으로 비용을 계산합니다.
        
        Args:
            usage (TokenUsage): 토큰 사용량 정보
            
        Returns:
            CostInfo: 계산된 비용 정보
        """
        model = usage.model
        # 기본 가격으로 폴백 (알 수 없는 모델의 경우)
        pricing = self.GEMINI_PRICING.get(model, {
            "input_tokens_per_1m": 1.00,
            "output_tokens_per_1m": 3.00,
        })
        
        # 비용 계산 (1M 토큰당 가격 기준)
        input_cost = (usage.input_tokens / 1_000_000) * pricing["input_tokens_per_1m"]
        output_cost = (usage.output_tokens / 1_000_000) * pricing["output_tokens_per_1m"]
        total_cost = input_cost + output_cost
        
        return CostInfo(
            input_cost=input_cost,
            output_cost=output_cost,
            total_cost=total_cost
        )
    
    def get_video_cost_summary(self, video_name: str) -> Dict:
        """
        특정 영상의 비용 요약을 반환합니다.
        
        Args:
            video_name (str): 영상 이름
            
        Returns:
            Dict: 비용 요약 정보
        """
        if video_name not in self.video_costs:
            return {
                "video_name": video_name,
                "total_requests": 0,
                "total_tokens": 0,
                "total_cost": 0.0,
                "details": []
            }
        
        usages = self.video_costs[video_name]
        total_cost = 0.0
        total_tokens = 0
        details = []
        
        for usage in usages:
            cost_info = self.calculate_cost(usage)
            total_cost += cost_info.total_cost
            total_tokens += usage.total_tokens
            
            details.append({
                "timestamp": usage.timestamp,
                "input_tokens": usage.input_tokens,
                "output_tokens": usage.output_tokens,
                "total_tokens": usage.total_tokens,
                "text_length": usage.text_length,
                "audio_duration": usage.audio_duration,
                "cost": cost_info.total_cost,
                "model": usage.model
            })
        
        return {
            "video_name": video_name,
            "total_requests": len(usages),
            "total_tokens": total_tokens,
            "total_cost": round(total_cost, 6),
            "details": details
        }
    
    def generate_cost_report(self) -> Dict:
        """
        전체 비용 보고서를 생성합니다.
        
        Returns:
            Dict: 전체 비용 보고서
        """
        report = {
            "session_info": {
                "session_start": self.session_start,
                "report_generated": datetime.now().isoformat(),
                "total_videos": len(self.video_costs)
            },
            "videos": {},
            "summary": {
                "total_requests": 0,
                "total_tokens": 0,
                "total_cost": 0.0
            }
        }
        
        for video_name in self.video_costs:
            video_summary = self.get_video_cost_summary(video_name)
            report["videos"][video_name] = video_summary
            
            report["summary"]["total_requests"] += video_summary["total_requests"]
            report["summary"]["total_tokens"] += video_summary["total_tokens"]
            report["summary"]["total_cost"] += video_summary["total_cost"]
        
        # 소수점 반올림
        report["summary"]["total_cost"] = round(report["summary"]["total_cost"], 6)
        
        return report
    
    def save_cost_report(self, filename: Optional[str] = None):
        """
        비용 보고서를 파일로 저장합니다.
        
        Args:
            filename (str, optional): 저장할 파일명. 기본값은 자동 생성
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"cost_report_{timestamp}.json"
        
        report = self.generate_cost_report()
        filepath = os.path.join(self.output_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"💰 비용 보고서 저장됨: {filepath}")
        
        # 간단한 요약도 텍스트로 저장
        summary_file = filepath.replace('.json', '_summary.txt')
        with open(summary_file, 'w', encoding='utf-8') as f:
            f.write("=== AI 더빙 비용 보고서 ===\n\n")
            f.write(f"세션 시작: {report['session_info']['session_start']}\n")
            f.write(f"보고서 생성: {report['session_info']['report_generated']}\n")
            f.write(f"처리된 영상 수: {report['session_info']['total_videos']}\n\n")
            
            f.write("=== 영상별 비용 ===\n")
            for video_name, video_data in report["videos"].items():
                f.write(f"\n📹 {video_name}:\n")
                f.write(f"  - 요청 횟수: {video_data['total_requests']}\n")
                f.write(f"  - 총 토큰: {video_data['total_tokens']:,}\n")
                f.write(f"  - 비용: ${video_data['total_cost']:.6f}\n")
            
            f.write(f"\n=== 전체 요약 ===\n")
            f.write(f"총 요청 횟수: {report['summary']['total_requests']}\n")
            f.write(f"총 토큰 사용량: {report['summary']['total_tokens']:,}\n")
            f.write(f"총 비용: ${report['summary']['total_cost']:.6f}\n")
        
        print(f"📋 요약 보고서 저장됨: {summary_file}")
        
        return filepath
    
    def print_cost_summary(self):
        """비용 요약을 콘솔에 출력합니다."""
        report = self.generate_cost_report()
        
        print("\n" + "="*50)
        print("🏷️  AI 더빙 비용 요약")
        print("="*50)
        
        for video_name, video_data in report["videos"].items():
            print(f"\n📹 {video_name}:")
            print(f"   요청: {video_data['total_requests']}회")
            print(f"   토큰: {video_data['total_tokens']:,}개")
            print(f"   비용: ${video_data['total_cost']:.6f}")
        
        print(f"\n💰 총 비용: ${report['summary']['total_cost']:.6f}")
        print("="*50)


# 전역 토큰 추적기 인스턴스
_global_tracker: Optional[TokenTracker] = None


def get_token_tracker(output_dir: str = "output") -> TokenTracker:
    """전역 토큰 추적기를 가져옵니다."""
    global _global_tracker
    if _global_tracker is None:
        _global_tracker = TokenTracker(output_dir)
    return _global_tracker


def reset_token_tracker():
    """전역 토큰 추적기를 리셋합니다."""
    global _global_tracker
    _global_tracker = None
