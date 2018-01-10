""" CartPole를 DQN(NIPS 2013)을 이용하여 학습시켜보겠습니다.  """

"""
앞에서 Q-Network는 아래의 문제점 때문에 학습을 원활하게 하지 못한다고 하였습니다.
이유는 두 가지였습니다.
Correlations between samples & Non-stationary targets

두 가지 이유에 대해서 Deep하게 설명해보겠습니다.

1. Correlations between samples
여기서는 막대기를 세울려고 하기 때문에 env가 대부분 비슷할 것입니다.

막대기를 세우기를 하면 루프를 5번 돌았다고 한다면 각각의 루프에서 받아오는 환경들은
상당히 유사하고 비슷비슷한 환경들이 돌아올겁니다.
왜냐하면 action에 따른 환경이 조금씩 조금씩만 바뀌기 때문입니다.(막대기를 세우려면)

따라서, 받아오는 data들 또한 굉장히 유사합니다. 그리고 받아오는 data들이 서로 연관성이 많습니다.

step에 따른 local index를 찍어보았을 때, 보통 linear regression이라고 한다면
비례하는 직선( / )이 나와야 학습이 잘 되었다라고 보는데
먄약 2개의 가까이 있는 data만(env만) 존재한다면 선은 어느 곳으로 튈지 모릅니다.
또한 4개의 점만 존재한다면 Optimer한 선은 달라질 것입니다.

2. Non-stationary targets
총 식을 코드로 표현하면 이렇습니다.
sess.run(train, feed_dict={X: x, Y: Q})이기 때문에

수학적인 최종 식은 loss = tf.reduce_sum(tf.square(Y - Qpred))

여기서 Y는
- 생성
Y = tf.placeholder(shape=[None, output_size], dtype=tf.float32)

- 쓰임
Q[0, action] = reward + dis * np.max(Q_next)

Qpred은
- 생성
X = tf.placeholder(tf.float32, [None, input_size], name="input_x")
W1 = tf.get_variable("W1", shape=[input_size, output_size],
                     initializer=tf.contrib.layers.xavier_initializer())
Qpred = tf.matmul(X, W1)

- 쓰임
x = np.reshape(state, [1, input_size])
입니다.

코드말고 식으로 보면, 같은 세타를 두고 있기 때문에 같은 W가 학습이 될 때마다 움직입니다.
마치 우리가 정확히 활을 쐈는데 과녁이 움직여버리는 현상이 나타납니다.

다시 말하자면, Qpred값은 Y값 쪽으로 가기 위해서 W(세타)를 업데이트 할 것입니다.
하지만 Qpred를 움직일수록 Y값도 같이 움직입니다. 이것이 두 번째 문제입니다.

다음으로 Solution을 세 가지로 살펴보겠습니다.

1. Go deep
말 그대로 deep하게 layer를 쌓으면서 고고!

2. Experience replay(correlations between samples의 해결책)
각 state마다 env에서 action을 한 값들
(state, action, reward, next_state, done)을 버퍼에 저장합니다.

버퍼에 있는 값들 중 랜덤하게 샘플들을 가져와서 학습합니다.
즉, minibatch와 같습니다.

랜덤하게 가져와서 학습을 하기 때문에 그래프가 / 가 될 확률이 더 높습니다.

3. Non-stationary targets
Network를 두 개를 만듭니다. 하나는 Qpred에 대한 w(세타), 나머지 하나는 Y에 대한 w(세타),
Y에 대한 세타는 가만히 두고, Qpred에 대한 w(세타)만 학습하도록 합니다.

이상 이론을 마치고, 코드랩을 진행해보겠습니다.

다음 코드는 NIPS 2013 DQN이므로 Solution에서 1, 2만을 사용합니다.
"""
import numpy as np
import tensorflow as tf
import random
import dqn
import gym
from collections import deque

env = gym.make('CartPole-v0')

INPUT_SIZE = env.observation_space.shape[0] # 4
OUTPUT_SIZE = env.action_space.n # 2

dis = 0.99
REPLAY_MEMORY = 50000

class DQN:
	def __init__(self, session, input_size, output_size, name = "main"):
		self.session = session
		self.input_size = input_size
		self.output_size = output_size
		self.net_name = name

		self._build_network()

	def _build_network(self, h_size = 10, l_rate = 1e-1):
		# h_size는 hidden size를 말합니다.
		with tf.variable_scope(self.net_name):
			self._X = tf.placeholder (
                tf.float32, [None, self.input_size], name="input_x")

			# First layer of weights
			W1 = tf.get_variable("W1", shape=[self.input_size, h_size],
				initializer=tf.contrib.layers.xavier_initializer())

			layer1 = tf.nn.tanh(tf.matmul(self._X, W1))

			# Second layer of weights
			W2 = tf.get_variable("W2", shape=[h_size,h_size],
				initializer=tf.contrib.layers.xavier_initializer())

			# Q preditction
			self._Qpred = tf.matmul(layer1, W2)

		# We need to define the parts of the network neede for learning a
		# policy
		self._Y = tf.placeholder(shape=[None, self.output_size], dtype = tf.float32)

		# Loss function
		self._loss = tf.reduce_mean(tf.square(self._Y - self._Qpred))
		# Learning
		self._train = tf.train.AdamOptimizer(learning_rate = l_rate).minimize(self._loss)


	def predict(self, state):
	"""
	예측 용도로 만든 코드입니다.
	위에 물론 self._Qpred가 있지만 모델 용도로 사용하고,
	predict로 따로 예측만 하도록 만듭니다.
	state값만 주면 예측을 합니다.

	이 함수는 Qpred에도 쓰이고, Y 즉, Q-learning 값을 구할 때도 사용됩니다.
	"""
		x = np.reshape(state, [1, self.input_size])
		return self.session.run(self._Qpred, feed_dict={self._X: x})

	def update(self, x_stack, y_stack):
	""" 학습 용도로 만든 코드입니다. x, y값만 필요합니다."""
		return self.session.run([self._loss, self._train],
			feed_dict={self._X: x_stack, self._Y: y_stack})

def simple_replay_train(DQN, train_batch):
	"""
	여기서 train_batch는 minibatch에서 가져온 data들입니다.
	x_stack은 state들을 쌓는 용도로이고,
	y_stack은 deterministic Q-learning 값을 쌓기 위한 용도입니다.

	우선 쌓기전에 비어있는 배열로 만들어놓기로 하죠.
	"""
	x_stack = np.empty(0).reshape(0, DQN.input_size)
	y_stack = np.empty(0).reshape(0, DQN.output_size)

	# Get stored information from the buffer
	"""for를 통해서 minibatch(train_batch)에서 가져온 값들을 하나씩 꺼냅니다."""
	for state, action, reward, next_state, done in tarin_batch:
		Q = DQN.predict(state)

		# terminal
		if done:
			Q[0, action] = reward
		else :
			# Obtain the Q' values by feeding the new state through our network
			Q[0, action] = reward + dis * np.max(DQN.predict(next_state))

		"""np.vstack는 y_stack에 쌓기 위한 numpy함수입니다."""
		y_stack = np.vstack([y_stack, Q])
		x_stack = np.vstack([x_stack, state])

	# Train our network using target and predicted Q values on each episode
	"""
	쌓은 stack들을 바로 update로 돌려서 학습을 시킵니다.
	학습은 위에서 만들었던 neural network(linear regression)을 통해서 학습이 되겠지요.
	"""
	return DQN.update(x_stack, y_stack)

def bot_play(mainDQN) :
	"""
	실제로 학습된 것으로 돌려보는 코드입니다.
	mainDQN 역시 학습된 network입니다.
	"""
	# See our trained network in action
	s = env.reset()
	reward_sum = 0

	while True:
		env.render()
		a = np.argmax(mainDQN.predict(s))
		s, reward, done, _ = env.step(a)
		reward_sum += reward
		if done:
			print "Total score: {}".format(reward_sum)
			break

def main():
	max_episodes = 5000

	# store the previous observations in replay memory
	"""python에 내장 되어있는 deque를 이용하여 buffer를 만듭니다."""
	replay_buffer = deque()

	with tf.Session() as sess :
		mainDQN = dqn.DQN(sess, input_size, output_size)
		# targetDQN = dqn.DQN(sess, input_size, output_size, name="target")
		tf.global_variables_initializer().run()

		for episode in range(max_episodes):
			e = 1. / ((episode / 10) + 1)
			done = False
			step_count = 0

			state = env.reset()

			while not done:
				if np.random.rand(1) < e :
					action = env.action_space.sample()
				else :
					# Choose an action by greedilty from the Q-network
					action = np.argmax(mainDQN.predict(state))

				# Get new state and reward from environment
				next_state, reward, done, _ = env.step(action)
				if done: # big penalty
					reward = -100

				# Save the experience to our buffer
				"""
				각 state마다 env에서 action을 한 값들
				(state, action, reward, next_state, done)을 버퍼에 저장하는 코드입니다.
				"""
				replay_buffer.append((state, action, reward, next_state, done))

				"""
				만약에 버퍼에 저장한 값이 너무 많으면 안되니까 REPLAY_MEMORY값을 넘으면
				맨 아래에 있던 값을 빼버리는(pop) 코드입니다.
				"""
				if len(replay_buffer) > REPLAY_MEMORY:
					replay_buffer.popleft()

				state = next_state
				step_count += 1
				if step_count > 10000: # Good enough
					break

			if step_count > 10000:
				pass
				break

			if episode % 10 == 1 : # train every 10 episodes
			"""
			max_episodes = 5000, for episode in range(max_episodes)
			일정 시간이 지나면, 일정 episode가 쌓이면 학습을 시켜야합니다.
			"""
				# Get a random batch of experiences.
				for _ in range(50):
					# Minibatch works better
					""""10개씩 가져와서 학습을 시킵니다."""
					minibatch = random.sample(replay_buffer, 10)
					loss, _ = simple_replay_train(mainDQN, minibatch)
				print "Loss: ", loss

		bot_play(mainDQN)

if __name__ == "__main__":
	main()