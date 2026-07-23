import random # Essential for sequence generation
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
from .models import Transaction, GameRound, User, PermanentCard
from .serializers import TransactionSerializer, GameRoundSerializer, UserSerializer
from decimal import Decimal
from django.shortcuts import get_object_or_404
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

# Logic to check if a board is a winner given the called numbers
def check_win_condition(board, called_numbers, pattern="Line"):
    # Fix: Safely convert dictionary board format ({'b': [...], 'i': [...]}) into a 2D matrix
    if isinstance(board, dict):
        if 'b' in board:
            board = [board['b'], board['i'], board['n'], board['g'], board['o']]
        elif '0' in board or 0 in board:
            board = [
                board.get(0) or board.get('0'),
                board.get(1) or board.get('1'),
                board.get(2) or board.get('2'),
                board.get(3) or board.get('3'),
                board.get(4) or board.get('4')
            ]

    called_set = set(called_numbers)
    # Checking Horizontal Rows
    for row_idx in range(5):
        is_winner = True
        for col_idx in range(5):
            cell = board[col_idx][row_idx]
            # Handle FREE space or special characters
            if cell == "FREE" or cell == "★": 
                continue
            if cell not in called_set:
                is_winner = False
                break
        if is_winner: 
            return True
    return False

# Custom JWT Serializer to include extra user info
class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["username"] = user.username
        token["is_agent"] = user.is_agent
        return token

class MyTokenObtainPairView(TokenObtainPairView):
    serializer_class = MyTokenObtainPairSerializer

# History of transactions for the logged-in agent
class TransactionListView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        user = request.user
        if not user.is_agent:
            return Response({"detail": "Only agents have transaction histories."}, status=status.HTTP_403_FORBIDDEN)
        qs = Transaction.objects.filter(agent=user).order_by("-timestamp")
        serializer = TransactionSerializer(qs, many=True)
        return Response(serializer.data)

# Launching a new game round
class CreateGameView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def post(self, request):
        user = request.user
        if not user.is_agent:
            return Response({"detail": "Only agents can create games."}, status=status.HTTP_403_FORBIDDEN)
        
        bet_amount_per_card = request.data.get("amount") 
        active_cards = request.data.get("active_cards", [])
        commission_percentage = request.data.get("commission_percentage", user.commission_percentage)

        if not active_cards or len(active_cards) < 3:
            return Response({"detail": "You must select at least 3 cards to start a game."}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            bet_amount_per_card = Decimal(str(bet_amount_per_card))
            comm_pct = Decimal(str(commission_percentage))
        except (TypeError, ValueError):
            return Response({"detail": "Invalid bet or commission amount."}, status=status.HTTP_400_BAD_REQUEST)
        
        total_collected = bet_amount_per_card * len(active_cards)
        commission_cost = total_collected * (comm_pct / Decimal('100'))
        
        if user.operational_credit < commission_cost:
            return Response({"detail": f"Insufficient credit. Commission Cost: {commission_cost}"}, status=status.HTTP_400_BAD_REQUEST)
        
        # Deduct commission from agent balance
        user.operational_credit -= commission_cost
        user.save()
        
        # --- OFFLINE FIX: Generate the entire calling sequence now ---
        # This allows the phone to download all 75 numbers and call them locally without internet.
        sequence = list(range(1, 76))
        random.shuffle(sequence)
        
        game_type = request.data.get("game_type", "Regular")
        
        Transaction.objects.create(
            agent=user, type="GAME_LAUNCH", amount=-commission_cost,
            running_balance=user.operational_credit, 
            note=f"{game_type} Launch ({len(active_cards)} cards at {bet_amount_per_card} ETB)"
        )
        
        game = GameRound.objects.create(
            agent=user, 
            game_type=game_type,
            winning_pattern=request.data.get("winning_pattern", "Line"),
            amount=bet_amount_per_card, 
            status="PENDING", 
            active_card_numbers=active_cards,
            commission_percentage=commission_percentage,
            called_numbers=sequence # Store the full sequence in the database
        )
        
        serializer = GameRoundSerializer(game)
        response_data = serializer.data
        # Explicitly send the calling sequence to the phone app for local playback
        response_data['calling_sequence'] = sequence 
        
        return Response(response_data, status=status.HTTP_201_CREATED)

# Fetch specific game details
class GameDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request, pk):
        game = get_object_or_404(GameRound, pk=pk)
        if request.user != game.agent and not request.user.is_staff:
            return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)
        serializer = GameRoundSerializer(game)
        return Response(serializer.data)

# Current logged in user info
class CurrentUserView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)

# List of past games for the agent
class GameHistoryView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        if not request.user.is_agent:
            return Response({"detail": "Only agents have a game history."}, status=status.HTTP_403_FORBIDDEN)
        games = GameRound.objects.filter(agent=request.user).order_by('-created_at')
        serializer = GameRoundSerializer(games, many=True)
        return Response(serializer.data)

# Verifying a winning claim
class CheckWinView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request, game_id, card_number):
        # Optional parameter 'balls_called' tells the server which ball the phone was on
        balls_called_count = request.query_params.get('balls_called')
        
        try:
            game = GameRound.objects.get(pk=game_id)
            card = PermanentCard.objects.get(card_number=card_number)
        except (GameRound.DoesNotExist, PermanentCard.DoesNotExist):
            return Response({"detail": "Game or Card not found."}, status=status.HTTP_404_NOT_FOUND)
        
        if card.card_number not in game.active_card_numbers:
            return Response({"detail": "Card not active in this game."}, status=status.HTTP_400_BAD_REQUEST)
        
        # Use only the portion of the sequence called on the phone at that time
        full_sequence = game.called_numbers
        if balls_called_count:
            try:
                effective_calls = full_sequence[:int(balls_called_count)]
            except ValueError:
                effective_calls = full_sequence
        else:
            effective_calls = full_sequence # Verify against all if not specified

        is_winner = check_win_condition(card.board, effective_calls, game.winning_pattern)
        
        return Response({
            'is_winner': is_winner,
            'card_number': card.card_number,
            'card_data': { 'board': card.board }
        })

# Adding a card after the game has already started
class AddCardToGameView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def post(self, request, game_id):
        user = request.user
        game = get_object_or_404(GameRound, pk=game_id)
        if game.agent != user:
            return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)
        
        card_num = request.data.get("card_number")
        try:
            card_num = int(card_num)
        except (TypeError, ValueError):
            return Response({"detail": "Invalid card number."}, status=status.HTTP_400_BAD_REQUEST)
            
        if card_num in game.active_card_numbers:
            return Response({"detail": "Card already active in this game."}, status=status.HTTP_400_BAD_REQUEST)
            
        # Deduct commission for this single late card
        comm_cost = Decimal(str(game.amount)) * (Decimal(str(game.commission_percentage)) / Decimal('100'))
        if user.operational_credit < comm_cost:
            return Response({"detail": "Insufficient credit for late card."}, status=status.HTTP_400_BAD_REQUEST)
            
        user.operational_credit -= comm_cost
        user.save()
        game.active_card_numbers.append(card_num)
        game.save()
        
        Transaction.objects.create(
            agent=user, type="LATE_CARD_ADD", amount=-comm_cost,
            running_balance=user.operational_credit, 
            note=f"Late card {card_num} added to Game #{game.id}"
        )
        
        serializer = GameRoundSerializer(game)
        return Response(serializer.data)
