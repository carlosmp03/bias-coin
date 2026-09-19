from typing import Literal, Optional

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

import database as db
from config import GEMINI_API_KEY, GEMINI_MODEL, RECENT_EVENTS_LIMIT


class AgentDecision(BaseModel):
    reply: str = Field(
        description="Короткий естественный ответ пользователю на русском."
    )
    action: Literal[
        "reply",
        "propose",
        "start",
        "snooze",
        "done",
        "cancel",
        "status",
    ] = "reply"

    task: Optional[str] = Field(
        default=None,
        description="Одно конкретное действие пользователя, если оно определено."
    )
    focus_minutes: Optional[int] = Field(
        default=None,
        ge=5,
        le=180,
        description="Длина ближайшего рабочего блока."
    )
    delay_minutes: Optional[int] = Field(
        default=None,
        ge=1,
        le=1440,
        description="Через сколько минут вернуться к пользователю."
    )
    memory_to_save: Optional[str] = Field(
        default=None,
        description=(
            "Только долговременная полезная информация: стабильная привычка, "
            "ограничение, учебная цель или предпочтение. Не сохраняй мелочи."
        )
    )


SYSTEM = """
Ты — личный Telegram-агент по организации учёбы и работы одного человека.

Твоя задача — НЕ быть чат-ботом, который долго рассуждает. Твоя задача —
добиваться перехода от слов к одному конкретному действию.

Принципы:
1. Обычно выбирай ОДНО ближайшее действие, а не список из 8 пунктов.
2. Если человек перечисляет много дел, помоги выбрать первое.
3. Если он явно готов начать — action=start.
4. Если дело сформулировано, но он ещё не начал — action=propose.
5. Если он просит вернуться через N минут — action=snooze.
6. Если сообщает, что закончил текущую задачу — action=done.
7. Если отказывается от текущей задачи — action=cancel.
8. Если просто рассуждает или вопрос недостаточно конкретен — action=reply.
9. Не создавай бессмысленные микрозадачи ради активности.
10. Не морализируй и не стыди. Можно быть настойчивым и лаконичным.
11. Не задавай три уточняющих вопроса подряд. Если можно принять разумное
    решение — прими его.
12. Нормальный фокус-блок: 25–45 минут. Если человек сопротивляется —
    10 минут. Если просит конкретную длительность — учитывай её.
13. Если человек говорит о математике, не решай за него автоматически.
    Помогай организовать работу; математическую подсказку давай только если
    он явно просит подсказку/проверку.
14. memory_to_save используй редко, только для устойчивых вещей.

Никогда не утверждай, что ты поставил таймер или напоминание сам:
ты только возвращаешь структурированное решение, а Python выполнит действие.
"""


def _state_text(user_id: int) -> str:
    c = db.active_commitment(user_id)
    s = db.active_session(user_id)
    mem = db.memories(user_id)
    events = db.recent_events(user_id, RECENT_EVENTS_LIMIT)

    lines = ["ТЕКУЩЕЕ СОСТОЯНИЕ:"]
    if c:
        lines.append(
            f"- Активное обязательство: {c['text']} (status={c['status']})"
        )
    else:
        lines.append("- Активного обязательства нет.")

    if s:
        lines.append(
            f"- Сессия: status={s['status']}, "
            f"focus_minutes={s['focus_minutes']}, due_at={s['due_at']}"
        )
    else:
        lines.append("- Активной сессии нет.")

    if mem:
        lines.append("- Долговременный контекст:")
        for m in reversed(mem):
            lines.append(f"  * {m['text']}")

    if events:
        lines.append("- Последние события:")
        for e in events:
            lines.append(
                f"  * {e['role']}/{e['event_type']}: {e['text']}"
            )

    return "\n".join(lines)


def decide(user_id: int, user_message: str) -> AgentDecision:
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not configured.")

    client = genai.Client(api_key=GEMINI_API_KEY)

    prompt = (
        SYSTEM
        + "\n\n"
        + _state_text(user_id)
        + "\n\nНОВОЕ СООБЩЕНИЕ ПОЛЬЗОВАТЕЛЯ:\n"
        + user_message
    )

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.35,
            response_mime_type="application/json",
            response_schema=AgentDecision,
        ),
    )

    return AgentDecision.model_validate_json(response.text)
