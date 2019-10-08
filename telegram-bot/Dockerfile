FROM python:3

RUN mkdir /bot
WORKDIR /bot
ADD ./* /bot/
RUN ls
RUN pip install -r requirements.txt

CMD [ "python", "bot.py" ]
