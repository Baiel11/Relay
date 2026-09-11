import uuid

from sqlalchemy.exc import IntegrityError

from app.core.exceptions import BadRequestException, ForbiddenException, NotFoundException
from app.models.conversation import Conversation
from app.repositories.conversation import ConversationRepository, PagedResult
from app.repositories.user import UserRepository
from app.schemas.conversation import ConversationListResponse, ConversationResponse
from app.schemas.user import UserBrief


class ConversationService:
    def __init__(
        self,
        conversation_repo: ConversationRepository,
        user_repo: UserRepository,
    ):
        self.conversation_repo = conversation_repo
        self.user_repo = user_repo


    async def get_or_create(
        self, current_user_id: uuid.UUID, other_user_id: uuid.UUID
    ) -> tuple[ConversationResponse, bool]:
        if current_user_id == other_user_id:
            raise BadRequestException(
                detail="Cannot start a conversation with yourself"
            )

        other = await self.user_repo.get_by_id(other_user_id)
        if not other:
            raise NotFoundException(detail="User not found")

        conversation = await self.conversation_repo.get_by_pair(
            current_user_id, other_user_id
        )
        if conversation:
            return await self._to_response(conversation, current_user_id), False

        try:
            conversation = await self.conversation_repo.create(
                current_user_id, other_user_id
            )
        except IntegrityError:
            await self.conversation_repo.db.rollback()
            conversation = await self.conversation_repo.get_by_pair(
                current_user_id, other_user_id
            )
            if conversation is None:
                raise
            return await self._to_response(conversation, current_user_id), False

        return await self._to_response(conversation, current_user_id), True


    async def list_for_user(
        self, user_id: uuid.UUID, limit: int = 50, offset: int = 0
    ) -> ConversationListResponse:
        result: PagedResult[Conversation] = await self.conversation_repo.list_for_user(
            user_id, limit=limit, offset=offset
        )
        items = [await self._to_response(c, user_id) for c in result.items]
        return ConversationListResponse(items=items, total=result.total)


    async def get_for_user(
        self, conversation_id: uuid.UUID, user_id: uuid.UUID
    ) -> Conversation:
        conversation = await self.conversation_repo.get_by_id(conversation_id)
        if conversation is None:
            raise NotFoundException(detail="Conversation not found")
        if user_id not in (conversation.participant_a, conversation.participant_b):
            raise ForbiddenException(
                detail="You are not a member of this conversation"
            )
        return conversation


    async def _to_response(
        self, conversation: Conversation, current_user_id: uuid.UUID
    ) -> ConversationResponse:
        other_id = (
            conversation.participant_b
            if conversation.participant_a == current_user_id
            else conversation.participant_a
        )
        other = await self.user_repo.get_by_id(other_id)
        return ConversationResponse(
            id=conversation.id,
            other_user=UserBrief.model_validate(other),
            created_at=conversation.created_at,
        )