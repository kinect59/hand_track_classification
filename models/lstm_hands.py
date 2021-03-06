# -*- coding: utf-8 -*-
"""
Created on Wed Nov  7 17:17:49 2018

define lstm model

@author: Γιώργος
"""

import torch
import torch.nn as nn
import torch.nn.functional as F

class LSTM_Hands(nn.Module):
    # source: https://github.com/yunjey/pytorch-tutorial/blob/master/tutorials/02-intermediate/bidirectional_recurrent_neural_network/main.py
    def __init__(self, input_size, hidden_size, num_layers, num_classes, **kwargs):
        super(LSTM_Hands, self).__init__()
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.dropout = kwargs.get('dropout')
        self.bidir = kwargs.get('bidir')
        self.noun_classes = kwargs.get('noun_classes')
        self.double_output = kwargs.get('double_output')

        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, 
                            bias=True, batch_first=False, dropout=0.0, bidirectional=self.bidir)
        self.dropout = nn.Dropout(p=self.dropout)
        
        output_features = hidden_size*2 if self.bidir else hidden_size
        self.fc = nn.Linear(output_features, num_classes)  
        if self.double_output:
            self.fc2 = nn.Linear(output_features, self.noun_classes)
    
    def forward(self, seq_batch_coords, seq_length):
        if self.bidir:
            return self.forward_bidir(seq_batch_coords, seq_length)
        else:
            return self.forward_onedir(seq_batch_coords, seq_length)
    
    def forward_bidir(self, seq_batch_coords, seq_lengths):
        batch_size = seq_batch_coords.size(1)
        h0 = torch.zeros(self.num_layers*2, batch_size, self.hidden_size).cuda()
        c0 = torch.zeros(self.num_layers*2, batch_size, self.hidden_size).cuda()
        
        packed_inputs = nn.utils.rnn.pack_padded_sequence(seq_batch_coords, seq_lengths)
        lstm_out, (hidden, cell) = self.lstm(packed_inputs, (h0, c0))
        unpacked_out, _ = nn.utils.rnn.pad_packed_sequence(lstm_out)
        
        out_for = unpacked_out[seq_lengths-1, list(range(batch_size)), :self.hidden_size]
        out_back = unpacked_out[0, list(range(batch_size)), self.hidden_size:]
        
        out = torch.cat((out_for, out_back), dim=-1)
        out = self.dropout(out)
        if self.double_output:
            out_verb = self.fc(out)
            out_noun = self.fc2(out)
            return out_verb, out_noun 
        else:    
            out = self.fc(out)
            return out

    def forward_onedir(self, seq_batch_coords, seq_lengths):
        # seq_batch_coords is sorted descending in sequence size so we can pad
        batch_size = seq_batch_coords.size(1)
        h0 = torch.zeros(self.num_layers, batch_size, self.hidden_size).cuda()
        c0 = torch.zeros(self.num_layers, batch_size, self.hidden_size).cuda()
        
        # choice 1
        packed_inputs = nn.utils.rnn.pack_padded_sequence(seq_batch_coords, seq_lengths)
        lstm_out, hidden = self.lstm(packed_inputs, (h0, c0))
        unpacked_out, dunno = nn.utils.rnn.pad_packed_sequence(lstm_out)
#       get the state of the hidden before the padded inputs start
        out = unpacked_out[seq_lengths-1, list(range(batch_size)), :]
        
        # choice 2 # all the sequences have the same length and each sequence step is forwarded explicitely
#        lstm_outs, hid = [], []
#        hidden = (h0, c0)
#        for seq_part in seq_batch_coords:
#            out, hidden = self.lstm(seq_part.unsqueeze(0), hidden)
#            lstm_outs.append(out)
#            hid.append(hidden)
#        out = torch.cat(lstm_outs, 0)
        
        # choice 3 # all sequences have the same length
#        lstm_out, hidden = self.lstm(seq_batch_coords, (h0, c0))
        
        # for choice 2 or 3
#        out = lstm_out[seq_lengths-1, list(range(batch_size)), :]

        out = self.dropout(out)        
        
        if self.double_output:
            out_verb = self.fc(out)
            out_noun = self.fc2(out)
            return out_verb, out_noun 
        else:    
            out = self.fc(out)
            return out

class LSTM_per_hand(nn.Module):
    def __init__(self, input_size, hidden_size, num_layers, num_classes, **kwargs):
        super(LSTM_per_hand, self).__init__()
        self.input_size = input_size
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.dropout = kwargs.get('dropout')
        
        self.left_lstm = nn.LSTM(input_size, hidden_size, num_layers,
                                 bias=True, batch_first=False, dropout=self.dropout,
                                 bidirectional=False)
        self.right_lstm = nn.LSTM(input_size, hidden_size, num_layers,
                                 bias=True, batch_first=False, dropout=self.dropout,
                                 bidirectional=False)       
        
        self.fc = nn.Linear(2*hidden_size, num_classes)

    def forward(self, seq_batch_coords, seq_lengths):
        batch_size = seq_batch_coords.size(1)
        # for dual lstm
        h0 = torch.zeros(self.num_layers, batch_size, self.hidden_size).cuda()
        c0 = torch.zeros(self.num_layers, batch_size, self.hidden_size).cuda()
        
        left_packed = nn.utils.rnn.pack_padded_sequence(seq_batch_coords[:,:,:self.input_size], seq_lengths)
        right_packed = nn.utils.rnn.pack_padded_sequence(seq_batch_coords[:,:,self.input_size:], seq_lengths)
        left_lstm_out, _ = self.left_lstm(left_packed, (h0, c0))
        right_lstm_out, _ = self.right_lstm(right_packed, (h0, c0))
        left_unpacked_out, _ = nn.utils.rnn.pad_packed_sequence(left_lstm_out)
        right_unpacked_out, _ = nn.utils.rnn.pad_packed_sequence(right_lstm_out)
        
        left_out = left_unpacked_out[seq_lengths-1, list(range(batch_size)), :]
        right_out = right_unpacked_out[seq_lengths-1, list(range(batch_size)), :] 
        out = torch.cat((left_out, right_out), dim=-1)
        
        out = self.fc(out)
        
        return out

class EncoderLSTM(nn.Module):
    def __init__(self, input_size, hidden_size, num_layers):
        super(EncoderLSTM, self).__init__()
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers)
        
    def forward(self, seq_batch_coords):
        batch_size = seq_batch_coords.size(1)
        h0 = torch.zeros(self.num_layers, batch_size, self.hidden_size).cuda()
        c0 = torch.zeros(self.num_layers, batch_size, self.hidden_size).cuda()
        output, (hn, cn) = self.lstm(seq_batch_coords, (h0, c0))
        return output, (hn, cn)
    
class AttnDecoderLSTM(nn.Module):
    def __init__(self, input_size, hidden_size, max_seq_len, num_classes):
        super(AttnDecoderLSTM, self).__init__()
        self.hidden_size = hidden_size
        self.max_seq_len = max_seq_len
        
        self.attn = nn.Linear(input_size + hidden_size, max_seq_len)
        self.attn_combine = nn.Linear(input_size + hidden_size, hidden_size)
        self.out = nn.Linear(hidden_size, num_classes)
        
    def forward(self, seq_batch_coords, lstm_out, seq_index):
        cat_for_attn = torch.cat((seq_batch_coords[seq_index], lstm_out[seq_index]), 1)
        attn_weights = self.attn(cat_for_attn)
        attn_weights = F.softmax(attn_weights, dim=1)
        
        attn_applied = torch.bmm(attn_weights.unsqueeze(1), 
                                 torch.transpose(lstm_out, 0, 1))        
#        attn_applied = torch.bmm(torch.transpose(attn_weights, 0, 1), 
#                                 torch.transpose(hidden, 0, 1))
        output = torch.cat((seq_batch_coords[seq_index], attn_applied[:,0,:]), 1)
        output = self.attn_combine(output)
        output = F.relu(output)
        
        output = self.out(output)
        
        return output, attn_weights
        
class LSTM_Hands_attn(nn.Module):
    def __init__(self, input_size, hidden_size, num_layers, num_classes, **kwargs):
        super(LSTM_Hands_attn, self).__init__()
#        dropout = kwargs.get('dropout')
        self.max_seq_len = kwargs.get('max_seq_len')

        self.encoder = EncoderLSTM(input_size, hidden_size, num_layers)
        self.decoder = AttnDecoderLSTM(input_size, hidden_size, self.max_seq_len, num_classes)
        
    def forward(self, seq_batch_coords, seq_lengths):
        seq_size = seq_batch_coords.size(0)
        assert seq_size == self.max_seq_len
        
        lstm_out, (hn, cn) = self.encoder(seq_batch_coords)
        outputs, attn_weights = [], []
        for seq_index in range(seq_size):
            fc_out, attn_weight = self.decoder(seq_batch_coords, lstm_out, seq_index)
            outputs.append(fc_out)
            attn_weights.append(attn_weight)
        # now for each step in the sequence I have a prediction based on the attention weights
        return outputs, attn_weights
        