import asyncio
import random

from aiohttp import ClientSession

from data import config
from utils.core import logger
from utils.telegram import AccountInterface


class RefCodeError(Exception):
    pass

class AccountUsedError(Exception):
    pass

class BlumBot:
    def __init__(
            self, 
            account: AccountInterface, 
            session: ClientSession
            ):
        """
        Initialize the BlumBot
        """
        self.account = account
        self.session = session
        self.refresh_token = ''

    async def logout(self):
        """
        Logout by closing the aiohttp session.
        """
        await self.session.close()

    async def claim_task(self, task: dict):
        """
        Claim a task given its task dictionary.
        """
        resp = await self.session.post(f'https://game-domain.blum.codes/api/v1/tasks/{task["id"]}/claim',
 ssl=False)
        resp_json = await resp.json()
        
        logger.debug(f"{self.account} | claim_task response: {resp_json}")

        return resp_json.get('status') == "CLAIMED"

    async def start_complete_task(self, task: dict):
        """
        Start a task given its task dictionary.
        """
        resp = await self.session.post(f'https://game-domain.blum.codes/api/v1/tasks/{task["id"]}/start',
 ssl=False)
        resp_json = await resp.json()

        logger.debug(f"{self.account} | start_complete_task response: {resp_json}")

    async def get_tasks(self):
        """
        Retrieve the list of available tasks.
        """
        resp = await self.session.get('https://game-domain.blum.codes/api/v1/tasks', ssl=False)
        resp_json = await resp.json()

        logger.debug(f"{self.account} | get_tasks response: {resp_json}")

        # Ensure the response is a list of tasks
        if isinstance(resp_json, list):
            return resp_json
        else:
            logger.error(f"{self.account} | Unexpected response format in get_tasks: {resp_json}")
            return []

    async def play_game(self, play_passes: int):
        """
        Play the game a specified number of times using available play passes.
        """
        while play_passes:
            try:
                await asyncio.sleep(random.uniform(*config.DELAYS['PLAY']))
                game_id = await self.start_game()

                if not game_id or game_id == "cannot start game":
                    logger.info(f"{self.account} | Couldn't start play in game! play_passes: {play_passes}")
                    break

                await asyncio.sleep(random.uniform(30, 40))

                msg, points = await self.claim_game(game_id)
                if isinstance(msg, bool) and msg:
                    logger.info(f"{self.account} | Finish play in game!; reward: {points}")
                else:
                    logger.info(f"{self.account} | Couldn't play game; msg: {msg} play_passes: {play_passes}")
                    break

                await asyncio.sleep(random.uniform(30, 40))

                play_passes -= 1

            except Exception as e:
                logger.error(f"{self.account} | Error occurred during play_game: {e}")
                await asyncio.sleep(random.uniform(*config.DELAYS['ERROR_PLAY']))

    async def claim_daily_reward(self):
        """
        Claim the daily reward.
        """
        resp = await self.session.post("https://game-domain.blum.codes/api/v1/daily-reward?offset=-180",
 ssl=False)
        txt = await resp.text()
        await asyncio.sleep(1)
        return True if txt == 'OK' else txt

    async def refresh(self):
        """
        Refresh the authorization token.
        """
        json_data = {'refresh': self.refresh_token}
        resp = await self.session.post("https://gateway.blum.codes/v1/auth/refresh", json=json_data, ssl=False)
        resp_json = await resp.json()

        self.session.headers['Authorization'] = "Bearer " + resp_json.get('access')
        self.refresh_token = resp_json.get('refresh')

    async def start_game(self):
        """
        Start a new game and return the game ID.
        """
        resp = await self.session.post("https://game-domain.blum.codes/api/v1/game/play", ssl=False)
        response_data = await resp.json()
        if "gameId" in response_data:
            return response_data.get("gameId")
        elif "message" in response_data:
            return response_data.get("message")

    async def claim_game(self, game_id: str):
        """
        Claim the reward for a completed game.
        """
        points = random.randint(*config.POINTS)
        json_data = {"gameId": game_id, "points": points}

        resp = await self.session.post("https://game-domain.blum.codes/api/v1/game/claim", json=json_data, ssl=False)
        if resp.status != 200:
            await asyncio.sleep(1)
            resp = await self.session.post("https://game-domain.blum.codes/api/v1/game/claim", json=json_data, ssl=False)
        
        txt = await resp.text()

        return True if txt == 'OK' else txt, points

    async def claim(self):
        """
        Claim the farming rewards.
        """
        resp = await self.session.post("https://game-domain.blum.codes/api/v1/farming/claim", ssl=False)
        if resp.status != 200:
            await asyncio.sleep(1)
            resp = await self.session.post("https://game-domain.blum.codes/api/v1/farming/claim", ssl=False)
        
        resp_json = await resp.json()

        return int(resp_json.get("timestamp")/1000), resp_json.get("availableBalance")

    async def start(self):
        """
        Start the farming process.
        """
        resp = await self.session.post("https://game-domain.blum.codes/api/v1/farming/start", ssl=False)

        if resp.status != 200:
            await asyncio.sleep(1)
            resp = await self.session.post("https://game-domain.blum.codes/api/v1/farming/start", ssl=False)

    async def friend_balance(self):
        """
        Gets friend balance
        """
        resp = await self.session.get("https://gateway.blum.codes/v1/friends/balance", ssl=False)
        resp_json = await resp.json()
        await asyncio.sleep(1)

        claim_amount = resp_json.get("amountForClaim")
        is_available = resp_json.get("canClaim")

        if resp.status != 200:
            resp = await self.session.get("https://gateway.blum.codes/v1/friends/balance", ssl=False)
            resp_json = await resp.json()
            claim_amount = resp_json.get("amountForClaim")
            is_available = resp_json.get("canClaim")

        return (claim_amount,
                is_available)
        
    async def get_referral_code(self) -> str:
        """
        Gets referral
        """
        resp = await self.session.get("https://gateway.blum.codes/v1/friends/balance", ssl=False)
        resp_json = await resp.json()

        referralToken = resp_json.get("referralToken")

        if resp.status != 200:
            await asyncio.sleep(1)
            resp = await self.session.get("https://gateway.blum.codes/v1/friends/balance", ssl=False)
            resp_json = await resp.json()
            referralToken = resp_json.get("referralToken")
        
        return referralToken

    async def friend_claim(self):
        resp = await self.session.post("https://gateway.blum.codes/v1/friends/claim", ssl=False)
        resp_json = await resp.json()
        amount = resp_json.get("claimBalance")
        if resp.status != 200:
            await asyncio.sleep(1)
            resp = await self.session.post("https://gateway.blum.codes/v1/friends/claim", ssl=False)
            resp_json = await resp.json()
            amount = resp_json.get("claimBalance")
        return amount

    async def balance(self):
        """
        Get the current balance and farming status.
        """
        resp = await self.session.get("https://game-domain.blum.codes/api/v1/user/balance", ssl=False)
        resp_json = await resp.json()
        await asyncio.sleep(1)
    
        timestamp = resp_json.get("timestamp")
        play_passes = resp_json.get("playPasses")
        
        start_time = None
        end_time = None
        if resp_json.get("farming"):
            start_time = resp_json["farming"].get("startTime")
            end_time = resp_json["farming"].get("endTime")
    
        return (int(timestamp / 1000) if timestamp is not None else None, 
                int(start_time / 1000) if start_time is not None else None, 
                int(end_time / 1000) if end_time is not None else None, 
                play_passes)

    async def login(self):
        """
        Login to the game using Telegram mini app authentication.
        """
        try:
            json_data = {"query": await self.account.get_tg_web_data()}
    
            resp = await self.session.post("https://gateway.blum.codes/v1/auth/provider/PROVIDER_TELEGRAM_MINI_APP",
                                           json=json_data, ssl=False)
            resp_json = await resp.json()
    
            self.session.headers['Authorization'] = "Bearer " + resp_json.get("token").get("access")
            self.refresh_token = resp_json.get("token").get("refresh")
            return True
        except:
            return False
        
    async def register(self, referral_code: str, username: str):
        """
        Register to the game using Telegram mini app authentication.
        """
        json_data = {
            "query": await self.account.get_tg_web_data(referral_code=referral_code),
            "referralToken": referral_code,
            "username": username
        }

        resp = await self.session.post("https://gateway.blum.codes/v1/auth/provider/PROVIDER_TELEGRAM_MINI_APP",
                                        json=json_data, ssl=False)
        resp_json = await resp.json()
        if 'limit' in await resp.text():
            raise RefCodeError('Referral token limit reached')
        elif 'already connected' in await resp.text():
            raise AccountUsedError('Account already connected')

        self.session.headers['Authorization'] = "Bearer " + resp_json.get("token").get("access")
        self.refresh_token = resp_json.get("token").get("refresh")
        return True
